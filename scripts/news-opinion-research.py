#!/usr/bin/env python3
"""Collect public reactions for a news URL/topic for Kurage Montage News.

This script belongs to kagentreach. It collects raw public signals from the
open web, YouTube, and X/browser-use when available. It does not fabricate
opinions; unavailable channels are returned as warnings so the caller can show
clear errors or partial research.
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = Path(os.environ.get("KURAGE_WORK_ROOT", "/home/kojima/work"))
X_SEARCH_SCRIPT = ROOT / "scripts" / "x-search-browser-use.py"
X_SEARCH_PYTHON = Path(os.environ.get(
    "KAGENTREACH_X_SEARCH_PYTHON",
    "/home/kojima/work/browser_agent/.venv/bin/python",
))
DEFAULT_X_COOKIE_FILE = Path(os.environ.get(
    "KAGENTREACH_X_COOKIE_FILE",
    "/home/kojima/work/browser_agent/chrome-profile/Default/Cookies",
))
DEFAULT_TWITTER_COOKIE_PYTHON = Path(os.environ.get(
    "KAGENTREACH_TWITTER_COOKIE_PYTHON",
    "/home/kojima/.local/pipx/venvs/twitter-cli/bin/python",
))


def run(args: list[str], *, timeout: int = 120, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True, timeout=timeout)


def clean_text(text: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit]


def build_query(url: str, title: str, query: str) -> str:
    if query.strip():
        return clean_text(query, 160)
    title = clean_text(title, 140)
    if title:
        return title
    parsed = urlparse(url)
    host = parsed.netloc.replace("www.", "")
    path_terms = " ".join([p for p in re.split(r"[-_/]+", parsed.path) if len(p) >= 3][:8])
    return clean_text(f"{host} {path_terms}", 160)


def is_yahoo_comments_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return host.endswith("news.yahoo.co.jp") and "/comments" in parsed.path


def is_x_status_url(url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    return (
        host in {"x.com", "twitter.com", "mobile.twitter.com"}
        or host.endswith(".x.com")
        or host.endswith(".twitter.com")
    ) and re.search(r"/(?:i/)?status(?:es)?/\d{12,22}|/i/status/\d{12,22}", parsed.path)


def extract_x_status_id(url: str) -> str:
    match = re.search(r"(?:status(?:es)?|i/status)/(\d{12,22})", url)
    if match:
        return match.group(1)
    match = re.search(r"(\d{12,22})", url)
    return match.group(1) if match else ""


def _as_int(value: Any) -> int:
    try:
        return int(str(value).replace(",", "").strip() or 0)
    except Exception:
        return 0


def _tweet_author(item: dict[str, Any]) -> str:
    author = item.get("author") if isinstance(item.get("author"), dict) else {}
    screen_name = author.get("screenName") or author.get("screen_name") or author.get("username") or ""
    name = author.get("name") or ""
    if screen_name:
        return f"@{str(screen_name).lstrip('@')}"
    return clean_text(str(name or "X"), 80)


def _tweet_likes(item: dict[str, Any]) -> int:
    metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
    for key in ("likes", "favorite_count", "favourites_count", "like_count"):
        if key in metrics:
            return _as_int(metrics.get(key))
        if key in item:
            return _as_int(item.get(key))
    return _as_int(item.get("likes") or item.get("favorites") or 0)


def load_x_cookie_env() -> tuple[dict[str, str], str]:
    """Load X auth cookies from the browser_agent Chrome profile without logging values."""
    if os.environ.get("TWITTER_AUTH_TOKEN") and os.environ.get("TWITTER_CT0"):
        return {}, ""
    cookie_file = DEFAULT_X_COOKIE_FILE
    if not cookie_file.exists():
        return {}, f"X cookie file not found: {cookie_file}"
    py = DEFAULT_TWITTER_COOKIE_PYTHON if DEFAULT_TWITTER_COOKIE_PYTHON.exists() else Path(sys.executable)
    code = r'''
import browser_cookie3
import json
import sys

cookie_file = sys.argv[1]
jar = browser_cookie3.chrome(cookie_file=cookie_file)
cookies = {}
for cookie in jar:
    domain = cookie.domain or ""
    if domain.endswith(".x.com") or domain.endswith(".twitter.com") or domain in ("x.com", "twitter.com", ".x.com", ".twitter.com"):
        if cookie.name in ("auth_token", "ct0"):
            cookies[cookie.name] = cookie.value
if "auth_token" in cookies and "ct0" in cookies:
    print(json.dumps(cookies))
'''
    try:
        proc = subprocess.run([str(py), "-c", code, str(cookie_file)], text=True, capture_output=True, timeout=30)
    except Exception as exc:
        return {}, f"X cookie extraction failed: {exc}"
    if proc.returncode != 0 or not proc.stdout.strip():
        return {}, clean_text(proc.stderr or "X auth cookies were not found in browser_agent profile", 800)
    try:
        data = json.loads(proc.stdout)
    except Exception:
        return {}, "X cookie extraction returned invalid JSON"
    auth_token = data.get("auth_token")
    ct0 = data.get("ct0")
    if not auth_token or not ct0:
        return {}, "X auth cookies were incomplete"
    return {"TWITTER_AUTH_TOKEN": str(auth_token), "TWITTER_CT0": str(ct0)}, ""


def fetch_x_replies(url: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    """Fetch direct replies to an X post through twitter-cli.

    The command requires an authenticated browser/cookie context. We intentionally
    return a clear error instead of fabricating reaction points when auth is
    missing, because kmontagenews videos should be based on real replies.
    """
    if not is_x_status_url(url):
        return [], {}, ""
    if not shutil.which("twitter"):
        return [], {}, "twitter-cli is not installed"
    tweet_id = extract_x_status_id(url)
    if not tweet_id:
        return [], {}, "tweet id was not found"
    max_count = max(limit * 3, 12)
    env = os.environ.copy()
    cookie_env, cookie_error = load_x_cookie_env()
    env.update(cookie_env)
    try:
        proc = subprocess.run(
            ["twitter", "tweet", tweet_id, "-n", str(max_count), "--json"],
            text=True,
            capture_output=True,
            timeout=180,
            env=env,
        )
    except Exception as exc:
        return [], {}, str(exc)
    raw = proc.stdout.strip()
    if proc.returncode != 0 and not raw:
        detail = clean_text(proc.stderr, 1000)
        if cookie_error and "No Twitter cookies found" in detail:
            detail = f"{detail} / {cookie_error}"
        return [], {}, detail
    try:
        data = json.loads(raw)
    except Exception:
        return [], {}, clean_text(proc.stderr or raw, 1200)
    if isinstance(data, dict) and data.get("ok") is False:
        err = data.get("error") if isinstance(data.get("error"), dict) else {}
        return [], {}, clean_text(err.get("message") or json.dumps(data, ensure_ascii=False), 1200)
    items = data if isinstance(data, list) else data.get("tweets") or data.get("results") or data.get("data") or []
    if not isinstance(items, list):
        return [], {}, "twitter-cli returned an unsupported JSON shape"

    original: dict[str, Any] = {}
    replies: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        text = clean_text(item.get("text") or item.get("full_text") or "", 520)
        if len(text) < 8:
            continue
        item_id = str(item.get("id") or "")
        author = _tweet_author(item)
        metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
        row = {
            "platform": "Xリプライ",
            "id": item_id,
            "author": author,
            "text": text,
            "url": f"https://x.com/i/status/{item_id}" if item_id else url,
            "like_count": _tweet_likes(item),
            "retweet_count": _as_int(metrics.get("retweets") or item.get("retweets") or item.get("rts") or 0),
            "reply_count": _as_int(metrics.get("replies") or item.get("replies") or 0),
            "posted_at": clean_text(item.get("createdAtLocal") or item.get("createdAt") or item.get("time") or "", 60),
        }
        if item_id == tweet_id or index == 0:
            original = row
            continue
        replies.append(row)
    original_handle = str(original.get("author") or "").lower()
    if original_handle.startswith("@"):
        replies = [
            row for row in replies
            if original_handle in str(row.get("text") or "").lower().split()[:3]
        ]
    replies.sort(key=lambda x: (int(x.get("like_count") or 0), int(x.get("retweet_count") or 0)), reverse=True)
    meta = {
        "tweet_id": tweet_id,
        "original_text": original.get("text", ""),
        "original_author": original.get("author", ""),
        "original_like_count": original.get("like_count", 0),
        "reply_total_fetched": len(replies),
    }
    return replies[:limit], meta, ""


def fetch_yahoo_comments(url: str, limit: int) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    if not is_yahoo_comments_url(url):
        return [], {}, ""
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept-Language": "ja,en;q=0.8",
        },
    )
    try:
        with urlopen(req, timeout=30) as res:
            raw = res.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return [], {}, str(exc)

    title_match = re.search(r'<meta\s+property=["\']og:title["\']\s+content=["\']([^"\']+)["\']', raw)
    page_title = clean_text(html.unescape(title_match.group(1)), 220) if title_match else ""
    state: dict[str, Any] = {}
    match = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*?\})\s*</script>", raw, flags=re.S)
    if match:
        try:
            state = json.loads(html.unescape(match.group(1)))
        except Exception:
            state = {}
    if not state:
        idx = raw.find('"userCommentList"')
        return [], {}, "Yahoo comments state JSON was not found" if idx < 0 else "Yahoo comments state JSON parse failed"

    article = state.get("article") if isinstance(state.get("article"), dict) else {}
    comment_list = state.get("userCommentList") if isinstance(state.get("userCommentList"), list) else []
    if not comment_list:
        # Some pages store comments below commentStore-like nested objects.
        def walk(obj: Any) -> list[dict[str, Any]]:
            if isinstance(obj, dict):
                if isinstance(obj.get("userCommentList"), list):
                    return obj["userCommentList"]
                for value in obj.values():
                    found = walk(value)
                    if found:
                        return found
            elif isinstance(obj, list):
                for value in obj:
                    found = walk(value)
                    if found:
                        return found
            return []
        comment_list = walk(state)

    comments: list[dict[str, Any]] = []
    for item in comment_list:
        if not isinstance(item, dict):
            continue
        text = clean_text(item.get("text") or "", 520)
        if len(text) < 20:
            continue
        comments.append({
            "platform": "Yahooコメント",
            "author": clean_text(item.get("name") or "", 60),
            "text": text,
            "url": item.get("permalink") or url,
            "empathy_count": int(item.get("empathyCount") or 0),
            "insight_count": int(item.get("insightCount") or 0),
            "negative_count": int(item.get("negativeCount") or 0),
            "reply_count": int(item.get("replyCount") or 0),
            "posted_at": clean_text(item.get("postDate") or "", 40),
        })
    comments.sort(key=lambda x: (int(x.get("empathy_count") or 0), int(x.get("insight_count") or 0)), reverse=True)
    meta = {
        "title": clean_text(article.get("title") or page_title, 180),
        "publisher": clean_text(article.get("providerName") or article.get("mediaName") or "", 80),
        "comment_total": state.get("parentOnlyCommentTotalCount") or len(comment_list),
    }
    return comments[:limit], meta, ""


def parse_mcporter_exa(stdout: str, limit: int) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for raw in stdout.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("Title:"):
            if current.get("title") or current.get("url"):
                items.append(current)
            current = {"title": line.replace("Title:", "", 1).strip()}
        elif line.startswith("URL:"):
            current["url"] = line.replace("URL:", "", 1).strip()
        elif line.startswith("Text:") or line.startswith("Snippet:") or line.startswith("Summary:"):
            current["snippet"] = line.split(":", 1)[1].strip()
        elif current and "snippet" not in current and len(line) > 40:
            current["snippet"] = line
    if current.get("title") or current.get("url"):
        items.append(current)
    cleaned = []
    seen = set()
    for item in items:
        url = item.get("url", "")
        key = url or item.get("title", "")
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append({
            "title": clean_text(item.get("title", ""), 180),
            "url": url,
            "snippet": clean_text(item.get("snippet", ""), 420),
        })
        if len(cleaned) >= limit:
            break
    return cleaned


def search_web(query: str, limit: int) -> tuple[list[dict[str, str]], str]:
    if not shutil.which("mcporter"):
        return [], "mcporter is not installed"
    # Add reaction/discussion terms so we collect opinions, not only duplicate news pages.
    q = f'{query} reactions opinions analysis discussion'
    try:
        proc = run(["mcporter", "call", f'exa.web_search_exa(query: "{q}", numResults: {limit})'], timeout=100, cwd=WORK_ROOT)
    except Exception as exc:
        return [], str(exc)
    if proc.returncode != 0:
        return [], clean_text(proc.stderr or proc.stdout, 1000)
    return parse_mcporter_exa(proc.stdout, limit), ""


def search_youtube(query: str, limit: int) -> tuple[list[dict[str, Any]], str]:
    if not shutil.which("yt-dlp"):
        return [], "yt-dlp is not installed"
    q = f"ytsearch{max(1, limit)}:{query} news reaction analysis"
    try:
        proc = run(["yt-dlp", "--dump-json", "--flat-playlist", "--no-warnings", q], timeout=120)
    except Exception as exc:
        return [], str(exc)
    if proc.returncode != 0 and not proc.stdout.strip():
        return [], clean_text(proc.stderr or proc.stdout, 1000)
    items: list[dict[str, Any]] = []
    for raw in proc.stdout.splitlines():
        try:
            data = json.loads(raw)
        except Exception:
            continue
        vid = data.get("id") or ""
        url = data.get("url") or (f"https://www.youtube.com/watch?v={vid}" if vid else "")
        items.append({
            "title": clean_text(data.get("title") or "", 180),
            "url": url,
            "channel": clean_text(data.get("channel") or data.get("uploader") or "", 120),
            "duration": data.get("duration"),
            "view_count": data.get("view_count"),
            "snippet": clean_text(data.get("description") or "", 420),
        })
        if len(items) >= limit:
            break
    return items, ""


def search_x(query: str, limit: int, mode: str) -> tuple[list[dict[str, Any]], str]:
    if not X_SEARCH_SCRIPT.exists():
        return [], f"X search script not found: {X_SEARCH_SCRIPT}"
    py = X_SEARCH_PYTHON if X_SEARCH_PYTHON.exists() else Path(sys.executable)
    out = Path(tempfile.mkdtemp(prefix="kagentreach-x-")) / "x.json"
    try:
        proc = run([str(py), str(X_SEARCH_SCRIPT), query, "-n", str(limit), "--mode", mode, "--json-out", str(out)], timeout=900, cwd=ROOT)
    except Exception as exc:
        return [], str(exc)
    if out.exists():
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
            if data.get("ok") and isinstance(data.get("results"), list):
                return data["results"][:limit], ""
            raw = data.get("raw")
            if data.get("ok") and isinstance(raw, str):
                try:
                    nested = json.loads(raw)
                    if isinstance(nested, dict) and nested.get("ok") and isinstance(nested.get("results"), list):
                        return nested["results"][:limit], ""
                except Exception:
                    pass
            return [], clean_text(json.dumps(data, ensure_ascii=False), 1000)
        except Exception:
            pass
    if proc.returncode != 0:
        return [], clean_text(proc.stderr or proc.stdout, 1000)
    try:
        data = json.loads(proc.stdout)
        return list(data.get("results") or [])[:limit], ""
    except Exception:
        return [], clean_text(proc.stdout or proc.stderr, 1000)


def opinion_points(
    web: list[dict[str, Any]],
    youtube: list[dict[str, Any]],
    x_results: list[dict[str, Any]],
    yahoo_comments: list[dict[str, Any]],
    x_replies: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    points: list[dict[str, str]] = []
    for item in x_replies or []:
        text = clean_text(item.get("text") or "", 280)
        if text:
            likes = int(item.get("like_count") or 0)
            label = f"いいね {likes}件"
            points.append({
                "platform": "Xリプライ",
                "point": f"{label}。{text}",
                "source_title": clean_text(item.get("author") or "Xリプライ", 120),
                "source_url": str(item.get("url") or ""),
                "like_count": str(likes),
            })
    for item in yahoo_comments:
        text = clean_text(item.get("text") or "", 260)
        if text:
            label = f"共感 {item.get('empathy_count', 0)}件"
            if item.get("insight_count"):
                label += f"、なるほど {item.get('insight_count')}件"
            points.append({
                "platform": "Yahooコメント",
                "point": f"{label}。{text}",
                "source_title": clean_text(item.get("author") or "Yahooコメント", 120),
                "source_url": str(item.get("url") or ""),
                "empathy_count": str(item.get("empathy_count") or 0),
            })
    for item in x_results:
        text = clean_text(item.get("text") or item.get("summary") or item.get("why_relevant") or "", 220)
        if text:
            points.append({"platform": "X", "point": text, "source_title": clean_text(item.get("author") or "X post", 80), "source_url": str(item.get("url") or "")})
    for item in youtube:
        title = clean_text(item.get("title") or "", 160)
        channel = clean_text(item.get("channel") or "", 80)
        if title:
            points.append({"platform": "YouTube", "point": f"{channel} は『{title}』という切り口で扱っています。" if channel else title, "source_title": title, "source_url": str(item.get("url") or "")})
    for item in web:
        snippet = clean_text(item.get("snippet") or item.get("title") or "", 220)
        if snippet:
            points.append({"platform": "Web/Blog", "point": snippet, "source_title": clean_text(item.get("title") or "", 120), "source_url": str(item.get("url") or "")})
    seen = set()
    unique = []
    for p in points:
        key = re.sub(r"\W+", "", p.get("point", "").lower())[:90]
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique[:18]


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect news reactions for Kurage Montage News")
    parser.add_argument("--url", required=True)
    parser.add_argument("--title", default="")
    parser.add_argument("--query", default="")
    parser.add_argument("--out", default="")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--x-mode", choices=("top", "latest"), default="top")
    parser.add_argument("--skip-x", action="store_true")
    args = parser.parse_args()

    query = build_query(args.url, args.title, args.query)
    limit = max(3, min(12, args.limit))
    errors: list[str] = []

    yahoo_comments, yahoo_meta, yahoo_error = fetch_yahoo_comments(args.url, limit)
    if yahoo_error:
        errors.append(f"yahoo_comments: {yahoo_error}")
    x_replies, x_reply_meta, x_reply_error = fetch_x_replies(args.url, limit)
    if x_reply_error:
        errors.append(f"x_replies: {x_reply_error}")

    web, web_error = search_web(query, limit)
    if web_error:
        errors.append(f"web: {web_error}")
    youtube, yt_error = search_youtube(query, min(6, limit))
    if yt_error:
        errors.append(f"youtube: {yt_error}")
    x_results: list[dict[str, Any]] = []
    if not args.skip_x:
        x_results, x_error = search_x(query, min(6, limit), args.x_mode)
        if x_error:
            errors.append(f"x: {x_error}")

    points = opinion_points(web, youtube, x_results, yahoo_comments, x_replies)
    result = {
        "ok": bool(points),
        "url": args.url,
        "query": query,
        "sources": {
            "yahoo_comments": yahoo_comments,
            "yahoo_meta": yahoo_meta,
            "x_replies": x_replies,
            "x_reply_meta": x_reply_meta,
            "web": web,
            "youtube": youtube,
            "x": x_results,
        },
        "opinion_points": points,
        "errors": errors,
        "summary": f"Yahooコメント {len(yahoo_comments)}件、Xリプライ {len(x_replies)}件、Web {len(web)}件、YouTube {len(youtube)}件、X検索 {len(x_results)}件から意見候補 {len(points)}件を収集しました。",
    }
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0 if points else 2


if __name__ == "__main__":
    raise SystemExit(main())
