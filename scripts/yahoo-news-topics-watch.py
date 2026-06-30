#!/usr/bin/env python3
"""Watch Yahoo News Topics and enqueue political/economy/IT items to Kurage Montage News.

Stable path: Yahoo News RSS categories. Optional path: X @YahooNewsTopics
when twitter-cli is authenticated. This script keeps its own processed URL
state so kdeck/rqdb4ai can run it frequently without duplicate videos.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - deployed env has bs4 via kmontage/kurage stack
    BeautifulSoup = None  # type: ignore

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = Path(os.environ.get("KAGENTREACH_YAHOO_NEWS_STATE", ROOT / "data" / "yahoo_news_topics_state.json"))
KMONTAGE_API = os.environ.get("KMONTAGE_API", "http://127.0.0.1:18305").rstrip("/")
USER_AGENT = "Mozilla/5.0 KurageAgentReach/1.0"

RSS_CATEGORIES = {
    "politics": "https://news.yahoo.co.jp/rss/topics/domestic.xml",
    "economy": "https://news.yahoo.co.jp/rss/topics/business.xml",
    "it": "https://news.yahoo.co.jp/rss/topics/it.xml",
}

POLITICS_KEYWORDS = (
    "国会", "政府", "首相", "総理", "官邸", "自民", "公明", "維新", "立民", "国民民主",
    "共産", "れいわ", "参院", "衆院", "選挙", "法案", "閣議", "大臣", "省", "庁",
    "防衛", "外交", "安全保障", "予算", "税", "補助金", "給付", "規制", "政策",
)
POLITICS_EXCLUDE = (
    "天気", "気温", "高温", "大雨", "台風", "地震", "火山", "警報", "熱中症",
    "事故", "火災", "逮捕", "殺人", "強盗", "熊", "クマ", "訃報", "芸能",
)


@dataclass
class Candidate:
    title: str
    category: str
    source_url: str
    article_url: str
    comments_url: str
    via: str


def clean_text(text: str, limit: int = 240) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def load_state(path: Path = STATE_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"processed": {}, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"processed": {}, "created_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if not isinstance(data.get("processed"), dict):
        data["processed"] = {}
    return data


def save_state(state: dict[str, Any], path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def fetch_text(url: str, timeout: int = 20) -> str:
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "ja,en;q=0.8"})
    with urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", errors="replace")


def normalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def comments_url_for_article(article_url: str) -> str:
    base = normalize_url(article_url)
    return base if base.endswith("/comments") else base + "/comments"


def category_allowed(category: str, title: str, url: str) -> bool:
    if category in {"economy", "it"}:
        return True
    if category != "politics":
        return False
    text = f"{title} {url}"
    if any(word in text for word in POLITICS_EXCLUDE):
        return False
    return any(word in text for word in POLITICS_KEYWORDS)


def resolve_article_url(url: str) -> tuple[str, str]:
    """Return (article_url, resolved_title)."""
    normalized = normalize_url(url)
    if "/articles/" in normalized:
        return normalized, ""
    html = fetch_text(url)
    title = ""
    if BeautifulSoup is None:
        m = re.search(r"https://news\.yahoo\.co\.jp/articles/[0-9a-f]+", html)
        return (m.group(0) if m else normalized), title
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", attrs={"property": "og:title"})
    if og and og.get("content"):
        title = clean_text(str(og.get("content")), 180)
    links: list[tuple[str, str]] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, str(a.get("href")))
        text = clean_text(a.get_text(" ", strip=True), 180)
        if "/articles/" in href and "/images/" not in href:
            links.append((normalize_url(href), text))
    if not links:
        return normalized, title
    # Prefer the explicit article body link, otherwise the first article link.
    for href, text in links:
        if "記事全文" in text or text == title or (title and text and text in title):
            return href, title or text
    return links[0][0], title or links[0][1]


def collect_rss_candidates(categories: list[str], limit_per_category: int) -> tuple[list[Candidate], list[str]]:
    candidates: list[Candidate] = []
    errors: list[str] = []
    for category in categories:
        rss_url = RSS_CATEGORIES.get(category)
        if not rss_url:
            errors.append(f"unknown category: {category}")
            continue
        try:
            raw = fetch_text(rss_url)
            root = ET.fromstring(raw)
            items = root.findall("./channel/item")[: max(1, limit_per_category)]
        except Exception as exc:
            errors.append(f"rss {category}: {exc}")
            continue
        for item in items:
            title = clean_text(item.findtext("title") or "", 180)
            link = clean_text(item.findtext("link") or "", 500)
            if not link or not category_allowed(category, title, link):
                continue
            try:
                article_url, resolved_title = resolve_article_url(link)
            except Exception as exc:
                errors.append(f"resolve {link}: {exc}")
                continue
            if "/articles/" not in article_url:
                continue
            candidates.append(Candidate(
                title=resolved_title or title,
                category=category,
                source_url=link,
                article_url=article_url,
                comments_url=comments_url_for_article(article_url),
                via="yahoo_rss",
            ))
    return dedupe_candidates(candidates), errors


def collect_x_candidates(limit: int) -> tuple[list[Candidate], list[str]]:
    """Best-effort X collection. Does not fail the watcher when auth is absent."""
    errors: list[str] = []
    try:
        proc = subprocess.run(
            ["twitter", "user-posts", "@YahooNewsTopics", "-n", str(max(1, limit))],
            text=True,
            capture_output=True,
            timeout=90,
        )
    except FileNotFoundError:
        return [], ["twitter-cli is not installed"]
    except Exception as exc:
        return [], [f"twitter user-posts failed: {exc}"]
    if proc.returncode != 0:
        return [], [clean_text(proc.stderr or proc.stdout, 1000)]
    urls = re.findall(r"https?://[^\s)\]}>'\"]+", proc.stdout)
    candidates: list[Candidate] = []
    for raw_url in urls:
        if "news.yahoo.co.jp" not in raw_url:
            continue
        raw_url = raw_url.rstrip(".,")
        try:
            article_url, title = resolve_article_url(raw_url)
        except Exception as exc:
            errors.append(f"x resolve {raw_url}: {exc}")
            continue
        text = f"{title} {article_url}"
        category = "it" if "/categories/it" in article_url or any(w in text for w in ["AI", "IT", "アプリ", "半導体", "マイクロソフト", "アップル"]) else "economy" if any(w in text for w in ["円", "株", "企業", "経済", "投資", "金融"]) else "politics"
        if not category_allowed(category, title, article_url):
            continue
        candidates.append(Candidate(
            title=title,
            category=category,
            source_url=raw_url,
            article_url=article_url,
            comments_url=comments_url_for_article(article_url),
            via="x_yahoo_news_topics",
        ))
    return dedupe_candidates(candidates), errors


def dedupe_candidates(candidates: list[Candidate]) -> list[Candidate]:
    seen: set[str] = set()
    out: list[Candidate] = []
    for c in candidates:
        key = normalize_url(c.article_url)
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def enqueue_kmontage_news(candidate: Candidate, timeout: int = 30) -> dict[str, Any]:
    import urllib.request

    payload = json.dumps({
        "url": candidate.comments_url,
        "mode": "news_opinions",
        "vtuber_mode": True,
        "video_style": "ai_avatar_news_explainer",
    }).encode("utf-8")
    req = Request(
        f"{KMONTAGE_API}/api/jobs",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urlopen(req, timeout=timeout) as res:
        text = res.read().decode("utf-8", errors="replace")
    data = json.loads(text)
    if not data.get("ok"):
        raise RuntimeError(text)
    return data


def run_watch(
    *,
    categories: list[str],
    max_enqueue: int,
    limit_per_category: int,
    include_x: bool,
    dry_run: bool,
    force: bool,
) -> dict[str, Any]:
    state = load_state()
    processed: dict[str, Any] = state.setdefault("processed", {})
    rss_candidates, rss_errors = collect_rss_candidates(categories, limit_per_category)
    x_candidates: list[Candidate] = []
    x_errors: list[str] = []
    if include_x:
        x_candidates, x_errors = collect_x_candidates(max(10, limit_per_category * len(categories)))
    candidates = dedupe_candidates([*rss_candidates, *x_candidates])
    selected: list[Candidate] = []
    skipped_processed = 0
    for candidate in candidates:
        key = normalize_url(candidate.article_url)
        if not force and key in processed:
            skipped_processed += 1
            continue
        selected.append(candidate)
        if len(selected) >= max_enqueue:
            break

    enqueued: list[dict[str, Any]] = []
    errors: list[str] = [*rss_errors, *x_errors]
    if not dry_run:
        for candidate in selected:
            key = normalize_url(candidate.article_url)
            try:
                result = enqueue_kmontage_news(candidate)
                record = {
                    **asdict(candidate),
                    "kmontage_job_id": result.get("job_id") or "",
                    "enqueued_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                enqueued.append(record)
                processed[key] = record
                save_state(state)
            except Exception as exc:
                errors.append(f"enqueue {candidate.comments_url}: {exc}")
    result = {
        "ok": dry_run or bool(enqueued) or not selected,
        "status": "dry_run" if dry_run else "ok",
        "checked": 1,
        "items": len(enqueued) if not dry_run else len(selected),
        "created": len(enqueued) if not dry_run else 0,
        "candidate_count": len(candidates),
        "selected_count": len(selected),
        "skipped_processed": skipped_processed,
        "categories": categories,
        "include_x": include_x,
        "dry_run": dry_run,
        "selected": [asdict(c) for c in selected],
        "enqueued": enqueued,
        "errors": errors,
        "state_path": str(STATE_PATH),
        "kmontage_api": KMONTAGE_API,
    }
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Watch YahooNewsTopics/Yahoo RSS and enqueue political/economy/IT news opinion videos.")
    parser.add_argument("--categories", default="politics,economy,it", help="Comma-separated: politics,economy,it")
    parser.add_argument("--max-enqueue", type=int, default=1)
    parser.add_argument("--limit-per-category", type=int, default=6)
    parser.add_argument("--include-x", action="store_true", help="Also inspect @YahooNewsTopics through twitter-cli when authenticated.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore processed URL state.")
    parser.add_argument("--out", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    categories = [c.strip() for c in args.categories.split(",") if c.strip()]
    result = run_watch(
        categories=categories,
        max_enqueue=max(1, args.max_enqueue),
        limit_per_category=max(1, args.limit_per_category),
        include_x=bool(args.include_x),
        dry_run=bool(args.dry_run),
        force=bool(args.force),
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
