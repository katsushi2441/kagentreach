#!/usr/bin/env python3
"""Daily monetization-video discovery and publishing pipeline.

Finds overseas long-form videos about Web3/Codex/Claude Code/vibe coding/AI
monetization, sends the best unused reference video to Kurage Montage, then
publishes an AI OSS technical article with the original video, extracted points,
and generated Kurage video URL.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import ssl
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = Path(os.environ.get("KAGENTREACH_MONETIZATION_STATE", ROOT / "data" / "monetization_daily_state.json"))
VWORK_DIR = Path(os.environ.get("VWORK_DIR", "/home/kojima/work/vwork"))
KMONTAGE_API = os.environ.get("KMONTAGE_API", "http://127.0.0.1:18305").rstrip("/")
AIXSNS_API = os.environ.get("AIXSNS_API", "https://aixec.exbridge.jp/api.php?path=posts")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://192.168.0.3:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:12b-it-qat")
BASE_ARTICLE_URL = "https://katsushi2441.github.io/vwork/articles"
KURAGE_URL = "https://kurage.exbridge.jp/kuragev.php"
DEFAULT_QUERIES = [
    "Claude Code make money SaaS 2026",
    "Codex Claude Code vibe coding make money SaaS",
    "vibe coding build sell app make money",
    "AI coding agency Claude Code make money",
    "Web3 AI agent crypto automation make money tutorial",
    "AI automation agency Claude Code YouTube monetization",
]
KEYWORDS = (
    "claude", "claude code", "codex", "vibe coding", "vibe coded",
    "ai agent", "ai automation", "saas", "web3", "crypto", "make money",
    "mrr", "arr", "sell", "agency", "youtube automation",
)


@dataclass
class Candidate:
    title: str
    url: str
    channel: str
    duration: float
    views: int
    upload_date: str
    description: str
    query: str
    score: float


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 600) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd or ROOT), text=True, capture_output=True, timeout=timeout, check=False)


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def today_jst() -> str:
    return time.strftime("%Y-%m-%d", time.localtime())


def now_jst() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())


def slugify(text: str, max_len: int = 42) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    text = re.sub(r"-+", "-", text)
    return (text or "ai-monetization-video")[:max_len].strip("-")


def http_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json", "User-Agent": "kagentreach-monetization/0.1"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as res:
        raw = res.read().decode("utf-8", errors="replace")
    parsed = json.loads(raw or "{}")
    return parsed if isinstance(parsed, dict) else {"raw": parsed}


def ollama_generate(prompt: str, *, format_json: bool = False, timeout: int = 240) -> str:
    url = OLLAMA_URL if OLLAMA_URL.endswith("/api/generate") else f"{OLLAMA_URL}/api/generate"
    payload: dict[str, Any] = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
    if format_json:
        payload["format"] = "json"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as res:
        data = json.loads(res.read().decode("utf-8", errors="replace") or "{}")
    return str(data.get("response") or "")


def search_youtube(query: str, limit: int = 8) -> list[Candidate]:
    proc = run([sys.executable, "-m", "yt_dlp", "--dump-json", "--flat-playlist", f"ytsearch{limit}:{query}"], timeout=180)
    candidates: list[Candidate] = []
    for line in proc.stdout.splitlines():
        try:
            item = json.loads(line)
        except Exception:
            continue
        title = str(item.get("title") or "").strip()
        vid = str(item.get("url") or item.get("id") or "").strip()
        url = str(item.get("webpage_url") or "")
        if not url and vid:
            url = "https://www.youtube.com/watch?v=" + vid
        if not title or not url:
            continue
        duration = float(item.get("duration") or 0)
        views = int(item.get("view_count") or 0)
        text = f"{title} {item.get('description') or ''}".lower()
        keyword_hits = sum(1 for kw in KEYWORDS if kw in text)
        score = keyword_hits * 1000 + min(views, 2_000_000) / 1000 + min(duration, 3600) / 60
        candidates.append(Candidate(
            title=title,
            url=url,
            channel=str(item.get("uploader") or item.get("channel") or ""),
            duration=duration,
            views=views,
            upload_date=str(item.get("upload_date") or ""),
            description=str(item.get("description") or ""),
            query=query,
            score=score,
        ))
    return candidates


def collect_candidates(queries: list[str], limit_per_query: int) -> list[Candidate]:
    by_url: dict[str, Candidate] = {}
    for query in queries:
        for candidate in search_youtube(query, limit=limit_per_query):
            if candidate.duration and candidate.duration < 600:
                continue
            if candidate.url not in by_url or candidate.score > by_url[candidate.url].score:
                by_url[candidate.url] = candidate
    return sorted(by_url.values(), key=lambda c: c.score, reverse=True)


def pick_candidate(candidates: list[Candidate], state: dict[str, Any], force_url: str = "") -> Candidate:
    if force_url:
        for candidate in candidates:
            if candidate.url == force_url:
                return candidate
        return Candidate(force_url, force_url, "", 0, 0, "", "", "forced", 999999)
    used = set(state.get("used_urls") or [])
    for candidate in candidates:
        if candidate.url not in used:
            return candidate
    raise RuntimeError("no unused monetization video candidates found")


def exa_supporting_sources(query: str, limit: int = 4) -> list[dict[str, str]]:
    if not shutil_which("mcporter"):
        return []
    proc = run(["mcporter", "call", f'exa.web_search_exa(query: "{query}", numResults: {limit})', "--timeout", "60000"], timeout=90)
    sources: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in proc.stdout.splitlines():
        line = raw.strip()
        if line.startswith("Title:"):
            if current:
                sources.append(current)
            current = {"title": line.replace("Title:", "", 1).strip()}
        elif line.startswith("URL:") and current:
            current["url"] = line.replace("URL:", "", 1).strip()
    if current:
        sources.append(current)
    return [s for s in sources if s.get("title") and s.get("url")][:limit]


def shutil_which(name: str) -> str:
    from shutil import which
    return which(name) or ""


def create_kmontage_video(candidate: Candidate, wait: bool, timeout_seconds: int) -> dict[str, Any]:
    created = http_json("POST", f"{KMONTAGE_API}/api/jobs", {"url": candidate.url, "vtuber_mode": True}, timeout=90)
    if not created.get("ok") or not created.get("job_id"):
        raise RuntimeError(f"kmontage enqueue failed: {created}")
    job_id = str(created["job_id"])
    result: dict[str, Any] = {"job_id": job_id, "status": "queued"}
    if not wait:
        return result
    deadline = time.time() + timeout_seconds
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = http_json("GET", f"{KMONTAGE_API}/api/jobs/{job_id}", timeout=40)
        status = str(last.get("status") or "")
        if status == "done":
            return last
        if status == "error":
            raise RuntimeError(f"kmontage failed: {last.get('error') or last}")
        time.sleep(20)
    raise RuntimeError(f"kmontage timed out job_id={job_id} last={last}")


def build_article(candidate: Candidate, kmontage_job: dict[str, Any], sources: list[dict[str, str]], slug: str) -> tuple[str, str]:
    video_url = str(kmontage_job.get("video_url") or "")
    reference = kmontage_job.get("reference_analysis") or {}
    scene_plan = kmontage_job.get("scene_plan") or {}
    qa = kmontage_job.get("qa") or {}
    title = f"海外で伸びるAI収益化動画を読む：{candidate.title[:52]}"
    prompt = f"""
あなたはAI OSS技術解説ブログの技術ライターです。
海外でバズっている長尺動画を紹介し、その要点をKurage Montageで日本語動画化した実例として記事を書いてください。

条件:
- 日本語
- 技術者向け
- 事実と数字を重視
- 「稼げる」と煽るだけにしない。再現条件、リスク、検証観点を書く
- 元動画URL、Kurage動画URL、Kurage Montageの処理内容を必ず入れる
- Markdown本文のみ。Front MatterとH1は不要

元動画:
タイトル: {candidate.title}
URL: {candidate.url}
チャンネル: {candidate.channel}
再生数: {candidate.views}
長さ: {round(candidate.duration / 60, 1)}分

Kurage Montage動画:
{video_url}

reference_analysis:
{json.dumps(reference, ensure_ascii=False)[:5000]}

scene_plan:
{json.dumps(scene_plan, ensure_ascii=False)[:3000]}

qa:
{json.dumps(qa, ensure_ascii=False)[:2500]}

補助資料:
{json.dumps(sources, ensure_ascii=False)}
"""
    try:
        body = ollama_generate(prompt, timeout=300).strip()
    except Exception as exc:
        print(f"[warn] ollama article generation failed: {exc}", file=sys.stderr)
        body = ""
    if not body:
        points = reference.get("key_points") or reference.get("facts") or []
        body = "\n".join([
            "## 元動画の概要",
            f"- 元動画: [{candidate.title}]({candidate.url})",
            f"- チャンネル: {candidate.channel or '不明'}",
            f"- 再生数: {candidate.views:,}",
            f"- 長さ: {round(candidate.duration / 60, 1)}分",
            "",
            "## Kurage Montageで生成した動画",
            f"- [Kurage動画]({video_url})",
            "",
            "## 抽出した要点",
            *(f"- {p}" for p in points[:8]),
            "",
            "## 技術的な見方",
            "Claude Code、Codex、バイブコーディング、AIエージェントによる収益化は、開発速度だけで成立するものではありません。市場選定、価格設計、配布チャネル、継続課金、運用コストの検証が必要です。",
        ])
    source_lines = "\n".join(f"- [{s['title']}]({s['url']})" for s in sources)
    appendix = f"""

## 今回の参照リンク

- 元動画: [{candidate.title}]({candidate.url})
- Kurage Montage生成動画: [{video_url}]({video_url})
- Kurage Montage: [katsushi2441/kmontage](https://github.com/katsushi2441/kmontage)
- Kurage Agent Reach: [katsushi2441/kagentreach](https://github.com/katsushi2441/kagentreach)

## 補助資料

{source_lines or "- なし"}
"""
    safe_title = title.replace('"', '\\"')
    fm = f"""---
title: "{safe_title}"
emoji: "💸"
type: "tech"
topics: [生成ai, claude, codex, 個人開発, web3]
published: true
---

# {title}

"""
    return title, fm + body + appendix


def update_articles_index(article_path: Path, title: str) -> None:
    index = VWORK_DIR / "articles.md"
    html = article_path.with_suffix(".html").name
    content = index.read_text(encoding="utf-8")
    if html in content:
        return
    lines = content.splitlines(keepends=True)
    item = f"- [{title}]({html})\n"
    for idx, line in enumerate(lines):
        if line.startswith("- ["):
            lines.insert(idx, item)
            break
    else:
        lines.append(item)
    index.write_text("".join(lines), encoding="utf-8")


def write_vwork_article(slug: str, title: str, body: str) -> Path:
    article_path = VWORK_DIR / "articles" / f"{today_jst()}-{slug}.md"
    suffix = 2
    while article_path.exists():
        article_path = VWORK_DIR / "articles" / f"{today_jst()}-{slug}-{suffix}.md"
        suffix += 1
    article_path.write_text(body, encoding="utf-8")
    update_articles_index(article_path, title)
    return article_path


def post_email_article(article_path: Path, title: str) -> dict[str, bool]:
    env_file = Path(os.environ.get("AIXEC_ENV_FILE", "/home/kojima/work/aixec/.env"))
    if env_file.exists():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    smtp_host = os.environ.get("SMTP_HOST", "mail18.heteml.jp")
    smtp_port = int(os.environ.get("SMTP_PORT", "465"))
    smtp_from = os.environ.get("SMTP_FROM", "")
    smtp_pass = os.environ.get("SMTP_PASSWORD", "")
    if not smtp_from or not smtp_pass:
        print("[warn] SMTP_FROM or SMTP_PASSWORD is missing; skip Hatena/Blogger cross-post", file=sys.stderr)
        return {"hatena": False, "blogger": False}
    text = article_path.read_text(encoding="utf-8")
    body = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S).lstrip()
    result = {"hatena": False, "blogger": False}
    try:
        import markdown  # type: ignore

        html_body = markdown.markdown(body, extensions=["extra", "tables"])
    except Exception:
        html_body = body
    for key, label, subtype, message_body in [
        ("HATENA_POST_EMAIL", "hatena", "html", html_body),
        ("BLOGGER_POST_EMAIL", "blogger", "plain", body),
    ]:
        to_addr = os.environ.get(key, "")
        if not to_addr:
            continue
        msg = MIMEText(message_body, subtype, "utf-8")
        msg["Subject"] = title
        msg["From"] = smtp_from
        msg["To"] = to_addr
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ssl.create_default_context()) as smtp:
            smtp.login(smtp_from, smtp_pass)
            smtp.sendmail(smtp_from, [to_addr], msg.as_bytes())
        result[label] = True
        time.sleep(2)
    return result


def post_aixsns(title: str, article_url: str, video_url: str, candidate: Candidate) -> dict[str, Any]:
    content = "\n".join([
        "AI OSS技術解説に、海外で伸びているAI/Claude Code/Codex/バイブコーディング収益化系の長尺動画を取り上げました。",
        "",
        title,
        "",
        f"記事: {article_url}",
        f"Kurage動画: {video_url}",
        f"元動画: {candidate.url}",
        "",
        "Kurage Agent Reachで候補を探し、Kurage Montageで要点動画化する日次パイプラインの実例です。",
    ])
    payload = {
        "author": "kurage",
        "title": title,
        "description": "海外AI収益化動画をKurage Montageで要点動画化し、AI OSS技術解説にまとめました。",
        "content": content,
        "kind": "ai_oss_monetization_video_digest",
        "source_url": article_url,
        "related_url": video_url,
    }
    return http_json("POST", AIXSNS_API, payload, timeout=30)


def git_commit_push_vwork(article_path: Path, commit: bool) -> None:
    if not commit:
        return
    rel = article_path.relative_to(VWORK_DIR)
    run(["git", "status", "--short", "--branch"], cwd=VWORK_DIR)
    pull = run(["git", "pull", "--rebase", "origin", "main"], cwd=VWORK_DIR, timeout=180)
    if pull.returncode != 0:
        raise RuntimeError(pull.stderr or pull.stdout)
    add = run(["git", "add", str(rel), "articles.md"], cwd=VWORK_DIR)
    if add.returncode != 0:
        raise RuntimeError(add.stderr or add.stdout)
    commit_proc = run(["git", "commit", "-m", f"Add AI monetization video digest: {article_path.stem}"], cwd=VWORK_DIR)
    if commit_proc.returncode != 0 and "nothing to commit" not in (commit_proc.stdout + commit_proc.stderr):
        raise RuntimeError(commit_proc.stderr or commit_proc.stdout)
    pull2 = run(["git", "pull", "--rebase", "origin", "main"], cwd=VWORK_DIR, timeout=180)
    if pull2.returncode != 0:
        raise RuntimeError(pull2.stderr or pull2.stdout)
    push = run(["git", "push"], cwd=VWORK_DIR, timeout=180)
    if push.returncode != 0:
        raise RuntimeError(push.stderr or push.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description="Daily AI/Web3/Codex/Claude monetization video digest worker")
    parser.add_argument("--limit-per-query", type=int, default=8)
    parser.add_argument("--query", action="append", default=[])
    parser.add_argument("--force-url", default="")
    parser.add_argument("--no-wait", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=5400)
    parser.add_argument("--no-email", action="store_true")
    parser.add_argument("--no-sns", action="store_true")
    parser.add_argument("--no-commit", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    state = read_json(STATE_PATH, {"runs": [], "used_urls": []})
    queries = args.query or DEFAULT_QUERIES
    candidates = collect_candidates(queries, args.limit_per_query)
    candidate = pick_candidate(candidates, state, args.force_url)
    supporting = exa_supporting_sources(f"{candidate.title} Claude Code SaaS monetization", limit=4)
    print(json.dumps({"selected": candidate.__dict__, "supporting": supporting}, ensure_ascii=False, indent=2))
    if args.dry_run:
        return

    kmontage_job = create_kmontage_video(candidate, wait=not args.no_wait, timeout_seconds=args.timeout_seconds)
    slug = slugify("ai-monetization-" + candidate.title)
    title, article = build_article(candidate, kmontage_job, supporting, slug)
    article_path = write_vwork_article(slug, title, article)
    article_url = f"{BASE_ARTICLE_URL}/{article_path.stem}.html"
    video_url = str(kmontage_job.get("video_url") or f"{KURAGE_URL}?id={kmontage_job.get('kurage_job_id', '')}")
    git_commit_push_vwork(article_path, commit=not args.no_commit)
    email_result = {} if args.no_email else post_email_article(article_path, title)
    sns_result = {} if args.no_sns else post_aixsns(title, article_url, video_url, candidate)
    run_record = {
        "created_at": now_jst(),
        "candidate": candidate.__dict__,
        "article_path": str(article_path),
        "article_url": article_url,
        "kmontage_job": kmontage_job.get("id") or kmontage_job.get("job_id"),
        "kurage_video_url": video_url,
        "email": email_result,
        "aixsns": sns_result,
    }
    state.setdefault("runs", []).insert(0, run_record)
    used = list(dict.fromkeys([candidate.url] + list(state.get("used_urls") or [])))
    state["used_urls"] = used[:500]
    write_json(STATE_PATH, state)
    print(json.dumps({"ok": True, **run_record}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
