#!/usr/bin/env python3
"""kmontage ニュース動画パイプラインが本当に動画を作れているかを見る。

watch_yahoo_news_topics_for_kmontage_job は「kmontage に何本渡したか」で成否を返す。
渡した先で失敗しても kdeck には「3/3 完了」と出るので、2026-09-09 の停電で
0.14 の Ollama が落ちたあと、7本連続で動画が作られないまま2日気づかなかった。

そこで渡した数ではなく **仕上がった数** を見る。直近のニュース動画ジョブを調べ、
末尾が連続で error なら異常として報告し、状態が変わったときだけメールを出す
（毎回出すと読まれなくなるので、壊れた時と直った時の2通だけ）。

  /usr/bin/python3 scripts/kmontage-news-health.py
  /usr/bin/python3 scripts/kmontage-news-health.py --no-email   # 確認だけ
"""
from __future__ import annotations

import argparse
import json
import smtplib
import ssl
import sys
import urllib.request
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = Path("/home/kojima/work/aixec/.env")
ALERT_TO = "katsushi2441@gmail.com"
MODE = "news_opinions"   # kmontage のニュース動画ジョブの目印


def load_env(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def fetch_jobs(api: str, limit: int) -> list[dict]:
    req = urllib.request.Request(f"{api.rstrip('/')}/api/jobs?limit={int(limit)}")
    with urllib.request.urlopen(req, timeout=30) as res:
        data = json.loads(res.read().decode("utf-8"))
    jobs = data.get("jobs") if isinstance(data, dict) else data
    return [j for j in (jobs or []) if j.get("mode") == MODE]


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(str(value)[:19], fmt)
        except ValueError:
            continue
    return None


def send_email(env: dict[str, str], subject: str, body: str) -> bool:
    host = env.get("SMTP_HOST")
    port = int(env.get("SMTP_PORT", "465"))
    user = env.get("SMTP_USER") or env.get("SMTP_FROM")
    pw = env.get("SMTP_PASSWORD")
    frm = env.get("SMTP_FROM", user)
    if not (host and user and pw):
        return False
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = frm
    msg["To"] = ALERT_TO
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=ctx, timeout=30) as s:
        s.login(user, pw)
        s.sendmail(frm, [ALERT_TO], msg.as_string())
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://127.0.0.1:18305")
    p.add_argument("--limit", type=int, default=60, help="kmontage から取るジョブ数")
    p.add_argument("--window-hours", type=float, default=36.0, help="この時間内のジョブだけ見る")
    p.add_argument("--max-consecutive-failures", type=int, default=2,
                   help="末尾がこの数だけ連続で error なら異常とみなす")
    p.add_argument("--state", type=Path, default=ROOT / "data" / "kmontage_news_health_state.json")
    p.add_argument("--no-email", action="store_true")
    args = p.parse_args()

    jobs = fetch_jobs(args.api, args.limit)
    jobs.sort(key=lambda j: str(j.get("created_at") or ""), reverse=True)
    since = datetime.now() - timedelta(hours=args.window_hours)
    recent = [j for j in jobs if (parse_ts(j.get("created_at")) or datetime.min) >= since]

    # 末尾（新しい順）に何本連続で error か。まだ動いている分は判定を待つので飛ばす
    consecutive = 0
    for j in recent:
        status = j.get("status")
        if status in ("done", "ok"):
            break
        if status == "error":
            consecutive += 1
            continue
        break   # queued/running は結果が出ていないので数えない

    done_jobs = [j for j in jobs if j.get("status") in ("done", "ok")]
    last_success = done_jobs[0] if done_jobs else None
    last_success_at = str(last_success.get("created_at")) if last_success else None
    stale_hours = None
    ts = parse_ts(last_success_at)
    if ts:
        stale_hours = round((datetime.now() - ts).total_seconds() / 3600, 1)

    healthy = consecutive < args.max_consecutive_failures
    last_error = ""
    if not healthy:
        for j in recent:
            if j.get("status") == "error":
                last_error = str(j.get("error") or "")[:400]
                break

    report = {
        "ok": True,
        "healthy": healthy,
        "checked": len(recent),
        "consecutive_failures": consecutive,
        "threshold": args.max_consecutive_failures,
        "window_hours": args.window_hours,
        "last_success_at": last_success_at,
        "hours_since_last_success": stale_hours,
        "last_error": last_error,
        "recent": [
            {"id": j.get("id"), "status": j.get("status"), "created_at": j.get("created_at")}
            for j in recent[:10]
        ],
    }

    # 状態が変わったときだけ知らせる（壊れた時と直った時の2通）
    args.state.parent.mkdir(parents=True, exist_ok=True)
    previous = {}
    if args.state.exists():
        try:
            previous = json.loads(args.state.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            previous = {}
    was_healthy = previous.get("healthy", True)
    changed = was_healthy != healthy
    report["state_changed"] = changed
    report["notified"] = False

    if changed and not args.no_email:
        env = load_env(ENV_PATH)
        if healthy:
            subject = "[復旧] kmontage ニュース動画が作れるようになりました"
            body = (
                f"直近{args.window_hours:.0f}時間のニュース動画が通るようになりました。\n"
                f"最後に成功したジョブ: {last_success_at}\n"
            )
        else:
            subject = f"[停止] kmontage ニュース動画が{consecutive}本連続で失敗しています"
            body = (
                f"直近{args.window_hours:.0f}時間で {consecutive} 本続けて失敗しました。\n"
                f"最後に成功したのは {last_success_at}"
                + (f"（{stale_hours}時間前）\n" if stale_hours is not None else "\n")
                + f"\n直近のエラー:\n{last_error}\n"
                "\n確認する場所:\n"
                "  1. 0.14 の Ollama:  curl -s http://192.168.0.14:11434/api/tags\n"
                "     （空の snap 版が 11434 を先に掴んで localhost だけで待ち受ける事故あり。\n"
                "       その場合は 0.14 で sudo snap remove ollama）\n"
                "  2. kmontage のジョブ: http://127.0.0.1:18305/api/jobs?limit=20\n"
                "  3. 失敗分の作り直し: kmontage で\n"
                "     /usr/bin/python3 scripts/retry_failed_jobs.py\n"
            )
        try:
            report["notified"] = send_email(env, subject, body)
        except Exception as exc:   # メールが出せなくても判定結果は返す
            report["email_error"] = str(exc)[:200]

    args.state.write_text(
        json.dumps({"healthy": healthy, "checked_at": datetime.now().isoformat(timespec="seconds"),
                    "consecutive_failures": consecutive, "last_success_at": last_success_at},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
