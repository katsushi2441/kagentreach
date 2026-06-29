#!/usr/bin/env python3
"""AI/Web3 monetization long-form video worker for Kurage Entertainment.

This replaces the daily war/geopolitics OSINT long-form slot with a safer
business/technology niche: Web3, crypto, Codex, Claude Code, AI agents, SNS
monetization, creator automation, OSS, and practical revenue systems.

YouTube is used for trend/reference metadata only. Video footage is collected
from license-explicit sources such as Wikimedia Commons, then transformed with
Japanese narration, overlays, Kurage avatar, YouTube upload, entertainment.php
publication, and AIxSNS announcement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

KURAGE_WEB_BACKEND = Path(os.environ.get("KURAGE_WEB_BACKEND", "/home/kojima/work/kurage_web/backend"))
if str(KURAGE_WEB_BACKEND) not in sys.path:
    sys.path.insert(0, str(KURAGE_WEB_BACKEND))

try:
    import geopolitics_video_jobs as geo  # type: ignore
except Exception as exc:  # pragma: no cover - configuration failure is surfaced at runtime.
    raise RuntimeError(f"failed to import shared Kurage video helpers: {exc}") from exc

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("KURAGE_WEB_DATA_DIR", "/home/kojima/work/kurage_web/data"))
ARTICLES_PATH = DATA_DIR / "entertainment_articles.json"
STATE_PATH = Path(os.environ.get("KAGENTREACH_AI_MONETIZATION_LONGFORM_STATE", DATA_DIR / "ai_monetization_longform_video_state.json"))
CANDIDATES_PATH = Path(os.environ.get("KAGENTREACH_AI_MONETIZATION_LONGFORM_CANDIDATES", DATA_DIR / "ai_monetization_longform_video_candidates.json"))
WORK_DIR = Path(os.environ.get("KAGENTREACH_AI_MONETIZATION_LONGFORM_WORK", DATA_DIR / "ai_monetization_longform_video_work"))
KURAGE_BASE = "https://kurage.exbridge.jp"
DEFAULT_AIXSNS_API = os.environ.get("AIXSNS_API", "https://aixec.exbridge.jp/api.php?path=posts")
DEFAULT_AIXSNS_DIRECT_API = os.environ.get("AIXSNS_DIRECT_API", "http://192.168.0.14:8081/posts")
DEFAULT_YOUTUBE_UPLOAD = Path(os.environ.get("YOUTUBE_UPLOAD_TOOL", "/home/kojima/work/airadio-scripted-mv/tools/youtube/upload_youtube.py"))
DEFAULT_YOUTUBE_CWD = Path(os.environ.get("YOUTUBE_UPLOAD_CWD", "/home/kojima/work/airadio-scripted-mv"))
DEFAULT_YOUTUBE_PYTHON = os.environ.get("YOUTUBE_UPLOAD_PYTHON", "/usr/bin/python3")
VIDEO_W = geo.VIDEO_W
VIDEO_H = geo.VIDEO_H
MAX_FOOTAGE_BYTES = int(os.environ.get("KAGENTREACH_AI_MONETIZATION_MAX_FOOTAGE_MB", "110")) * 1024 * 1024

DEFAULT_TOPIC = "AI/Web3/Codex/Claude Code/SNS収益化とOSS実装解説"
DEFAULT_QUERY = "Claude Code Codex AI agents Web3 crypto YouTube automation creator monetization make money tutorial 2026"
DEFAULT_COMMONS_CATEGORIES = [
    "Category:Videos of computers",
    "Category:Videos of computer screens",
    "Category:Videos of software",
    "Category:Videos of mobile phones",
    "Category:Videos of offices",
    "Category:Videos of people using computers",
    "Category:Videos of Bitcoin",
    "Category:Videos of cryptocurrency",
    "Category:Videos of conferences",
    "Category:Videos of data centers",
]
TOPIC_PROFILES: list[dict[str, Any]] = [
    {
        "id": "ai_coding_business",
        "topic": "CodexとClaude Codeで作るAI開発副業・小規模SaaS収益化",
        "query": "Claude Code Codex build SaaS make money AI coding agency automation 2026",
        "categories": ["Category:Videos of computers", "Category:Videos of computer screens", "Category:Videos of software", "Category:Videos of offices"],
        "chapters": ["導入", "なぜ伸びるか", "案件化できる作業", "OSSと自動化", "収益導線", "リスク", "実装手順", "まとめ"],
        "fallback_title": "CodexとClaude Codeで作る、AI開発副業の実践設計",
        "summary": "AIコーディング、OSS、ブラウザ自動化、動画/SNS運用を組み合わせ、小さく収益化する流れを整理します。",
        "focus": "AIコーディング、受託、小規模SaaS、OSS活用、ブラウザ自動化、継続収益",
    },
    {
        "id": "sns_creator_automation",
        "topic": "YouTube・X・Threads・TikTokをつなぐAI動画/SNS収益化パイプライン",
        "query": "YouTube automation AI video X Threads TikTok monetization workflow Claude Code",
        "categories": ["Category:Videos of mobile phones", "Category:Videos of computer screens", "Category:Videos of software", "Category:Videos of offices"],
        "chapters": ["導入", "ショート動画の需要", "自動化の構成", "SNS導線", "分析と改善", "リスク", "運用設計", "まとめ"],
        "fallback_title": "AI動画とSNSをつなぐ、収益化パイプラインの作り方",
        "summary": "動画生成、SNS投稿、分析、再投稿までを一つの運用ループとして設計する考え方を解説します。",
        "focus": "YouTube Shorts、X、Threads、TikTok、Instagram、AI動画生成、自動投稿、分析改善",
    },
    {
        "id": "web3_crypto_content",
        "topic": "Web3・クリプト・AIエージェント時代の情報発信と収益化",
        "query": "Web3 crypto AI agent content monetization YouTube automation creator economy",
        "categories": ["Category:Videos of Bitcoin", "Category:Videos of cryptocurrency", "Category:Videos of computer screens", "Category:Videos of conferences"],
        "chapters": ["導入", "市場の注目点", "信頼の作り方", "コンテンツ型収益", "自動化", "注意点", "実践手順", "まとめ"],
        "fallback_title": "Web3とAIエージェントで考える、情報発信の収益化戦略",
        "summary": "Web3や暗号資産の話題を、投機ではなく情報発信・教育コンテンツ・分析サービスとして組み立てます。",
        "focus": "Web3、暗号資産、AIエージェント、教育コンテンツ、分析、リスク説明、信頼形成",
    },
    {
        "id": "oss_productization",
        "topic": "OSSを組み合わせて作るAIプロダクトと収益化の実装戦略",
        "query": "open source AI tools productize make money Claude Code Codex automation",
        "categories": ["Category:Videos of software", "Category:Videos of computer screens", "Category:Videos of computers", "Category:Videos of conferences"],
        "chapters": ["導入", "OSSの価値", "組み合わせ方", "プロダクト化", "販売導線", "運用", "法務と品質", "まとめ"],
        "fallback_title": "OSSをプロダクト化する、AI時代の実装と収益化",
        "summary": "OSSを単に使うだけでなく、顧客課題に合わせて組み合わせ、運用可能なサービスへ変える設計を解説します。",
        "focus": "OSS、AIエージェント、プロダクト化、ライセンス、保守、導入支援、収益化",
    },
]
PRODUCTION_NOTE_TERMS = (
    "素材のライセンス", "ライセンス確認", "利用条件", "使用素材", "出典", "再利用コンテンツ",
    "この動画では", "本動画では", "映像素材として", "素材として", "YouTube上", "Wikimedia Commons",
)
MIN_EXPLANATORY_CHARS = 1100
SUSPICIOUS_SCRIPT_TERMS = ("Projected.com", "outsourcing and", "small SaaS production", "個人Projected", "http://", "https://")


def now_jst() -> str:
    return datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(value: str, prefix: str = "aimon") -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(cmd: list[str], *, cwd: Path | None = None, timeout: int = 600, input_text: str | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd or ROOT), input=input_text, text=True, capture_output=True, timeout=timeout, check=False, env=env)


def plain_text(text: Any, limit: int | None = None) -> str:
    value = geo.plain_text(text, limit=None)
    return value[:limit].rstrip() if limit else value


def normalize_space(text: Any) -> str:
    return geo.normalize_space(text)


def select_topic_profile(topic: str | None = None) -> dict[str, Any]:
    requested = normalize_space(topic or "")
    if requested and requested not in {DEFAULT_TOPIC, "auto", "自動"}:
        return {
            "id": "custom",
            "topic": requested,
            "query": DEFAULT_QUERY,
            "categories": DEFAULT_COMMONS_CATEGORIES,
            "chapters": ["導入", "背景", "市場の構造", "実装例", "収益導線", "リスク", "実践手順", "まとめ"],
            "fallback_title": f"AI/Web3収益化解説: {requested}",
            "summary": "AI、OSS、動画、SNS、自動化を組み合わせ、収益化につなげる実装戦略を解説します。",
            "focus": requested,
        }
    state = read_json(STATE_PATH, {"runs": []})
    recent_ids = [str(item.get("profile_id") or "") for item in state.get("runs", [])[: len(TOPIC_PROFILES) - 1]]
    for profile in TOPIC_PROFILES:
        if profile["id"] not in recent_ids:
            return dict(profile)
    return dict(TOPIC_PROFILES[0])


def collect_youtube_references(query: str = DEFAULT_QUERY, limit: int = 12) -> list[dict[str, Any]]:
    return geo.collect_youtube_references(query, limit=limit)


def collect_commons_candidates(categories: list[str], limit: int = 24) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_category = max(4, min(12, limit))
    for category in categories:
        if len(found) >= limit:
            break
        try:
            items = geo.collect_commons_candidates(categories=[category], limit=per_category)
        except Exception:
            continue
        for item in items:
            size = int(item.get("size") or 0)
            if size and size > MAX_FOOTAGE_BYTES:
                continue
            cid = str(item.get("candidate_id") or item.get("source_url") or item.get("media_url") or "")
            if not cid or cid in seen:
                continue
            seen.add(cid)
            title_desc = f"{item.get('title') or ''} {item.get('description') or ''}".lower()
            tech_bonus = sum(8 for term in ("computer", "screen", "software", "phone", "bitcoin", "crypto", "office", "conference", "data", "laptop") if term in title_desc)
            item["score"] = int(item.get("score") or 0) + tech_bonus
            found.append(item)
            if len(found) >= limit:
                break
    found.sort(key=lambda x: (x.get("score") or 0, x.get("width") or 0), reverse=True)
    return found[:limit]


def collect_sources_job(target_count: int = 24, query: str = DEFAULT_QUERY, categories: list[str] | None = None, profile_id: str = "", **_: Any) -> dict[str, Any]:
    categories = categories or DEFAULT_COMMONS_CATEGORIES
    existing = read_json(CANDIDATES_PATH, [])
    by_id = {str(c.get("candidate_id") or ""): c for c in existing if isinstance(c, dict) and c.get("candidate_id")}
    commons = collect_commons_candidates(categories=categories, limit=target_count)
    refs = collect_youtube_references(query, limit=12)
    added = 0
    for item in commons + refs:
        cid = item.get("candidate_id") or slugify(str(item.get("url") or item.get("source_url") or item.get("title") or "candidate"))
        item["candidate_id"] = cid
        if profile_id:
            item.setdefault("profile_id", profile_id)
        if cid not in by_id:
            by_id[cid] = item
            added += 1
    merged = list(by_id.values())
    merged.sort(key=lambda x: (x.get("kind") == "footage", x.get("score") or 0, x.get("collected_at") or ""), reverse=True)
    write_json(CANDIDATES_PATH, merged[:500])
    return {"ok": True, "status": "ok", "items": added, "created": added, "footage": len(commons), "youtube_references": len(refs), "path": str(CANDIDATES_PATH), "profile_id": profile_id, "query": query, "categories": categories}


def scene_label(candidate: dict[str, Any]) -> str:
    text = f"{plain_text(candidate.get('title'))} {plain_text(candidate.get('description'))}".lower()
    if "bitcoin" in text or "crypto" in text or "blockchain" in text:
        return "暗号資産とWeb3の市場イメージ"
    if "screen" in text or "software" in text or "program" in text or "code" in text:
        return "AIツールとソフトウェア開発の画面"
    if "phone" in text or "mobile" in text or "smartphone" in text:
        return "SNS運用とモバイル視聴の現場"
    if "office" in text or "laptop" in text or "computer" in text:
        return "AIを使った開発・業務自動化の現場"
    if "conference" in text or "presentation" in text:
        return "AI/Web3市場の発表・カンファレンス"
    if "data center" in text or "server" in text:
        return "AIサービスを支えるクラウド基盤"
    return "AIとデジタルビジネスの実写素材"


def build_material_digest(footage: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()
    for item in footage:
        label = scene_label(item)
        if label not in seen:
            labels.append(label)
            seen.add(label)
        if len(labels) >= 6:
            break
    return labels


def clean_narration(text: str) -> str:
    text = plain_text(text)
    sentences = [s.strip() for s in re.split(r"(?<=[。！？])", text) if s.strip()]
    kept: list[str] = []
    previous = ""
    for sentence in sentences:
        if any(term in sentence for term in PRODUCTION_NOTE_TERMS):
            continue
        if len(re.findall(r"[A-Za-z][A-Za-z\s,.'’-]{28,}", sentence)):
            continue
        compact = re.sub(r"\s+", "", sentence)
        if previous and compact == previous:
            continue
        kept.append(sentence)
        previous = compact
    return "".join(kept)


def ensure_narration_length(narration: str, topic: str, target_minutes: int) -> str:
    target_chars = max(2600, int(target_minutes) * 300)
    text = clean_narration(narration)
    extensions = [
        "重要なのは、AIツールを単なる話題で終わらせず、仕事の流れに組み込むことです。調査、要約、台本、ブラウザ操作、動画生成、SNS投稿、分析までを一つのループにすると、個人でも小さなメディア事業に近い動きができます。",
        "収益化を考えるときは、広告収入だけを見ると不安定です。受託、教材、テンプレート、運用代行、分析レポート、ツール提供のように、複数の導線を持つ方が現実的です。",
        "CodexやClaude Codeの価値は、コードを書く速さだけではありません。試作、検証、改善、公開までの距離を短くし、失敗した企画を早く捨てられることにあります。これは小規模事業者にとって大きな武器です。",
        "一方で、誇張した収益事例をそのまま信じるのは危険です。再生数、登録者数、販売導線、制作本数、改善回数、外注費を分けて見ないと、本当に再現できるモデルか判断できません。",
        "実践の第一歩は、伸びているテーマを観察し、自分の言葉で要点を整理し、短い動画と記事に変換することです。そこから反応を見て、次の台本、サムネイル、投稿先を改善していきます。",
    ]
    idx = 0
    while len(text) < target_chars:
        text += extensions[idx % len(extensions)]
        idx += 1
    return text


def validate_narration_content(text: str) -> None:
    cleaned = clean_narration(text)
    if len(cleaned) < MIN_EXPLANATORY_CHARS:
        raise ValueError(f"AI monetization narration is too thin: {len(cleaned)} chars")
    bad = ("地政学", "紛争", "戦争", "ウクライナ", "防空", "ミサイル", "戦況")
    hits = [term for term in bad if term in cleaned]
    if hits:
        raise ValueError(f"wrong niche terms leaked into narration: {hits[:5]}")
    if any(term in cleaned for term in SUSPICIOUS_SCRIPT_TERMS):
        raise ValueError("suspicious generated text leaked into narration")
    if re.search(r"[A-Za-z][A-Za-z0-9 .,/&()_-]{45,}", cleaned):
        raise ValueError("narration contains a long raw English fragment")


def validate_summary_content(text: str) -> None:
    cleaned = plain_text(text)
    if len(cleaned) < 20:
        raise ValueError("summary is too short")
    if any(term in cleaned for term in SUSPICIOUS_SCRIPT_TERMS):
        raise ValueError("suspicious generated text leaked into summary")
    if re.search(r"[A-Za-z][A-Za-z0-9 .,/&()_-]{35,}", cleaned):
        raise ValueError("summary contains a long raw English fragment")


def generate_script(topic: str, references: list[dict[str, Any]], target_minutes: int = 10, footage: list[dict[str, Any]] | None = None, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    footage = footage or []
    profile = profile or {}
    refs_text = "\n".join(f"- {plain_text(r.get('title'), 120)}" for r in references[:8])
    materials_text = "\n".join(f"- {label}" for label in build_material_digest(footage))
    chapters_text = "、".join(profile.get("chapters") or ["導入", "背景", "市場の構造", "実装例", "収益導線", "リスク", "まとめ"])
    focus_text = plain_text(profile.get("focus") or topic, 220)
    prompt = f"""
あなたは日本語のAIビジネス解説番組の構成作家です。
テーマ: {topic}
今回の焦点: {focus_text}
使える実写・画面系素材の内容:
{materials_text}
海外で伸びている参考動画タイトル（読み上げ禁止。傾向分析だけに使う）:
{refs_text}

必ず守ること:
- 日本語で、経営者・個人開発者・副業開発者に役立つ10分前後の解説にする。
- 戦争、軍事、地政学、OSINTの話にしない。
- URLや英語タイトルをアルファベットで読み上げない。
- 「稼げます」と煽るだけにしない。再現条件、作業手順、リスク、改善ループを具体化する。
- Codex、Claude Code、OSS、ブラウザ自動化、YouTube、X、Threads、Instagram、TikTok、Web3、暗号資産を必要に応じてつなぐ。
- 構成は、{chapters_text}。章ごとに具体例を入れる。
- JSONだけで返す。title, summary, narration, chapters を持つ。
""".strip()
    ollama_url = os.environ.get("OLLAMA_URL", "http://192.168.0.14:11434/api/generate")
    if not ollama_url.endswith("/api/generate"):
        ollama_url = ollama_url.rstrip("/") + "/api/generate"
    model = os.environ.get("OLLAMA_MODEL", "gemma4:12b-it-qat")
    try:
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False, "format": "json"}, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(ollama_url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=300) as res:
            data = json.loads(res.read().decode("utf-8", errors="replace") or "{}")
        parsed = json.loads(data.get("response") or "{}")
        if parsed.get("title") and parsed.get("narration"):
            narration = ensure_narration_length(str(parsed.get("narration") or ""), topic, target_minutes)
            validate_narration_content(narration)
            parsed["narration"] = narration
            parsed["title"] = plain_text(parsed.get("title"), 72)
            parsed["summary"] = plain_text(parsed.get("summary") or "AI、OSS、動画、SNS、自動化を組み合わせた収益化戦略を整理します。", 160)
            validate_summary_content(str(parsed["summary"]))
            return parsed
    except Exception:
        pass
    return build_fallback_script(topic, references, target_minutes, footage, profile)


def build_fallback_script(topic: str, references: list[dict[str, Any]], target_minutes: int, footage: list[dict[str, Any]] | None = None, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or {}
    labels = build_material_digest(footage or []) or ["AI開発の画面", "SNS運用", "Web3市場", "OSSプロダクト化"]
    title = plain_text(profile.get("fallback_title") or f"AI/Web3収益化の実装戦略: {topic}", 72)
    summary = plain_text(profile.get("summary") or "AI、OSS、動画、SNS、自動化を組み合わせ、現実的に収益化するための流れを解説します。", 160)
    focus = plain_text(profile.get("focus") or topic)
    sections = [
        f"今回は、{topic}をテーマに、AIとOSSを使った収益化の流れを整理します。焦点は、{focus}です。単に流行語を追うのではなく、何を作り、どこで見せ、どう改善し、どこで収益につなげるかを順番に見ます。",
        f"画面で扱う素材は、{ '、'.join(labels[:4]) }です。ここから見たいのは、AIツールそのものではなく、仕事の流れがどこまで短くなるかです。調査、台本、実装、動画、SNS、分析をつなげると、一人でも小さなメディア運用や開発サービスを回せます。",
        "最初のポイントは、CodexやClaude Codeを、コードを書く道具だけで終わらせないことです。仕様を整理し、試作品を作り、画面を録画し、説明記事を書き、SNSで反応を見る。この一連の工程を短くすることに価値があります。",
        "次に、収益化の入口を複数に分けます。YouTubeの広告だけではなく、開発受託、テンプレート販売、運用代行、教材、レポート、SaaSの月額課金を組み合わせます。どれか一つが外れても、事業全体が止まりにくくなります。",
        "Web3や暗号資産のテーマでは、投資を煽るよりも、情報整理と教育の価値が重要です。新しいツール、ウォレット、AIエージェント、トークン経済の変化を、初心者にも理解できる形で説明できれば、信頼が蓄積します。",
        "SNS運用では、YouTube、X、Threads、Instagram、TikTokを同じ内容で機械的に流すだけでは弱いです。長尺で背景を説明し、ショートで要点を切り出し、記事で検索に残し、SNSで会話を作る。この役割分担が必要です。",
        "実装面では、OSSを活用するほど速度は上がります。ただし、ライセンス、保守、データの扱い、ログの確認、公開前の品質チェックは省けません。自動化は、雑に作るためではなく、検証回数を増やすために使うべきです。",
        "最後に、伸びた事例を見るときは、数字の裏側を分解します。再生数だけではなく、制作本数、編集時間、投稿頻度、販売導線、外注費、継続率を見ます。ここまで分解して初めて、自分の事業に移植できるか判断できます。",
        "まとめると、AI時代の収益化は、魔法のツールを一つ見つけることではありません。調査、制作、投稿、分析、改善を小さく回し、反応があるテーマへ集中することです。Codex、Claude Code、OSS、SNSをつなぐほど、小さなチームでも事業を前に進められます。",
    ]
    narration = ensure_narration_length("".join(sections), topic, target_minutes)
    validate_narration_content(narration)
    return {"title": title, "summary": summary, "narration": narration, "chapters": profile.get("chapters") or ["導入", "背景", "実装", "収益導線", "リスク", "まとめ"]}


def prepare_clip(src: Path, out: Path, seconds: float, caption: str) -> Path:
    return geo.prepare_clip(src, out, seconds, caption)


def build_video(topic: str, script: dict[str, Any], candidates: list[dict[str, Any]], work: Path, target_minutes: int = 10) -> Path:
    narration = normalize_space(script.get("narration") or script.get("summary") or topic)
    audio = geo.synthesize_tts(narration, work / "narration.mp3")
    audio_duration = geo.ffprobe_duration(audio)
    target_seconds = max(float(target_minutes * 60), audio_duration + 8.0 if audio_duration else float(target_minutes * 60))
    selected = [
        c for c in candidates
        if c.get("kind") == "footage"
        and c.get("media_url")
        and (not int(c.get("size") or 0) or int(c.get("size") or 0) <= MAX_FOOTAGE_BYTES)
    ]
    if len(selected) < 3:
        raise RuntimeError("not enough licensed AI/Web3 footage candidates")
    random.shuffle(selected)
    clip_count = max(6, min(int(os.environ.get("KAGENTREACH_AI_MONETIZATION_CLIP_COUNT", "8")), len(selected)))
    per_clip = target_seconds / clip_count
    prepared: list[Path] = []
    source_notes: list[str] = []
    for idx, cand in enumerate(selected[:clip_count]):
        ext = Path(urllib.parse.urlparse(cand["media_url"]).path).suffix or ".webm"
        src = work / "sources" / f"clip_{idx:02d}{ext}"
        if src.exists() and int(cand.get("size") or 0) and src.stat().st_size < int(cand.get("size") or 0):
            src.unlink()
        if not src.exists():
            geo.download_file(cand["media_url"], src)
        caption = scene_label(cand)
        prepared.append(prepare_clip(src, work / "clips" / f"clip_{idx:02d}.mp4", per_clip, caption))
        source_notes.append(f"{plain_text(cand.get('title'), 140)} / {cand.get('license')} / {plain_text(cand.get('artist') or cand.get('credit') or 'Wikimedia Commons', 120)} / {cand.get('source_url')}")
    concat = work / "concat.txt"
    concat.write_text("".join(f"file '{p}'\n" for p in prepared), encoding="utf-8")
    bg = work / "background.mp4"
    proc = run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(bg)], timeout=900)
    if proc.returncode != 0:
        raise RuntimeError("concat failed: " + proc.stderr[-1000:])
    title = normalize_space(script.get("title") or topic)[:70]
    subtitle = "AI/Web3収益化とOSS実装を、実写素材と日本語解説で整理"
    overlay = geo.make_overlay_png(work / "final_overlay.png", [title, subtitle], position="bottom")
    out_raw = work / "ai_monetization_longform.raw.mp4"
    proc = run([
        "ffmpeg", "-y", "-i", str(bg), "-i", str(audio), "-i", str(overlay), "-shortest",
        "-filter_complex", "[0:v][2:v]overlay=0:0[v]", "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out_raw),
    ], timeout=3600)
    if proc.returncode != 0 or not out_raw.exists():
        raise RuntimeError("final render failed: " + proc.stderr[-1200:])
    out = work / "ai_monetization_longform.mp4"
    geo.apply_vtuber_avatar_overlay(out_raw, out)
    write_json(work / "sources.json", source_notes)
    return out


def upload_youtube(video: Path, title: str, description: str) -> dict[str, Any]:
    if not DEFAULT_YOUTUBE_UPLOAD.exists():
        raise RuntimeError(f"YouTube uploader not found: {DEFAULT_YOUTUBE_UPLOAD}")
    out_dir = DEFAULT_YOUTUBE_CWD / "storage" / "youtube"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_out = out_dir / f"ai_monetization_{slugify(str(video), 'yt')}_response.json"
    upload_env = os.environ.copy()
    upload_env.pop("PYTHONHOME", None)
    upload_env.pop("PYTHONPATH", None)
    upload_env["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:" + upload_env.get("PATH", "")
    proc = run([
        DEFAULT_YOUTUBE_PYTHON, str(DEFAULT_YOUTUBE_UPLOAD), str(video),
        "--title", title[:100],
        "--description", plain_text(description, 4500),
        "--tags", "AI,Codex,Claude Code,Web3,クリプト,YouTube収益化,SNS運用,OSS,Kurage,エクスブリッジ",
        "--privacy", os.environ.get("KAGENTREACH_AI_MONETIZATION_YOUTUBE_PRIVACY", "public"),
        "--category-id", os.environ.get("KAGENTREACH_AI_MONETIZATION_YOUTUBE_CATEGORY", "28"),
        "--json-out", str(json_out),
    ], cwd=DEFAULT_YOUTUBE_CWD, timeout=2400, env=upload_env)
    if proc.returncode != 0:
        raise RuntimeError("YouTube upload failed: " + (proc.stderr or proc.stdout)[-1500:])
    data = read_json(json_out, {})
    video_id = data.get("id")
    if not video_id:
        raise RuntimeError("YouTube response did not contain id")
    return {"youtube_video_id": video_id, "youtube_url": f"https://youtu.be/{video_id}", "response": data, "json_out": str(json_out)}


def publish_article(topic: str, script: dict[str, Any], upload: dict[str, Any], sources: list[dict[str, Any]]) -> dict[str, Any]:
    articles = read_json(ARTICLES_PATH, [])
    title = normalize_space(script.get("title") or f"AI/Web3収益化解説: {topic}")
    slug = slugify("ai-monetization:" + title + upload["youtube_url"], "aimon")
    summary = normalize_space(script.get("summary") or "AI、OSS、動画、SNS、自動化を組み合わせた収益化戦略を整理する長尺解説です。")
    page_body = [
        "この動画は、戦争OSINT枠の代替として、AI、Web3、Codex、Claude Code、SNS運用、OSS実装をテーマにした長尺解説として生成しました。",
        "海外で伸びている動画タイトルや市場トレンドを参考にしつつ、映像素材はライセンス確認済みの実写・画面系素材を使い、独自の日本語ナレーションで再構成しています。",
        "YouTube、X、Threads、Instagram、TikTok、ブログ、OSSをどうつなげて収益化ループを作るかを、実装・運用・改善の観点で整理しています。",
    ]
    article = {
        "slug": slug,
        "title": title,
        "summary": summary,
        "body": page_body,
        "content_category": "AI・Web3・収益化解説",
        "topic_tags": ["AI", "Web3", "Codex", "Claude Code", "SNS収益化", "OSS"],
        "source_name": "Kurage AI/Web3 Monetization Longform Worker",
        "source_title": topic,
        "source_url": upload["youtube_url"],
        "youtube_url": upload["youtube_url"],
        "youtube_video_id": upload["youtube_video_id"],
        "youtube_uploaded_at": now_jst(),
        "created_at": now_jst(),
        "updated_at": now_jst(),
        "safety_note": "YouTube参考動画はトレンド分析のみ。映像はライセンス確認済み素材を使い、独自解説として編集しています。",
        "source_materials": sources[:20],
    }
    articles = [a for a in articles if a.get("slug") != slug]
    articles.insert(0, article)
    write_json(ARTICLES_PATH, articles[:500])
    return article


def build_announcement(article: dict[str, Any]) -> str:
    page_url = f"{KURAGE_BASE}/entertainment.php?id={article['slug']}"
    return "\n".join([
        "AI/Web3収益化の長尺解説動画を公開しました。",
        "",
        article.get("title") or "",
        "",
        article.get("summary") or "",
        "",
        f"記事・YouTube再生窓: {page_url}",
        f"YouTube: {article.get('youtube_url') or ''}",
    ])


def post_aixsns(article: dict[str, Any]) -> dict[str, Any]:
    if os.environ.get("KAGENTREACH_AI_MONETIZATION_ANNOUNCE_AIXSNS", "1") == "0":
        return {"skipped": True, "reason": "disabled"}
    content = build_announcement(article)
    payload = {
        "author": "kurage",
        "title": "AI/Web3収益化解説動画を公開しました",
        "description": article.get("summary") or "",
        "content": content,
        "kind": "ai_web3_monetization_longform_video",
        "source_url": f"{KURAGE_BASE}/entertainment.php?id={article['slug']}",
        "related_url": article.get("youtube_url") or "",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    token = (os.environ.get("AIXEC_API_TOKEN") or os.environ.get("AIXEC_MARKET_REGISTER_TOKEN") or "").strip()
    if token:
        headers["Authorization"] = "Bearer " + token
        headers["X-AIXEC-API-TOKEN"] = token
    errors: list[str] = []
    parsed: dict[str, Any] = {}
    for url in [DEFAULT_AIXSNS_API, DEFAULT_AIXSNS_DIRECT_API]:
        if not url:
            continue
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as res:
                parsed = json.loads(res.read().decode("utf-8", errors="replace") or "{}")
            break
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    else:
        raise RuntimeError("AIxSNS post failed: " + " | ".join(errors)[-1000:])
    item = parsed.get("item") if isinstance(parsed, dict) else {}
    return {
        "skipped": False,
        "id": item.get("id") if isinstance(item, dict) else None,
        "url": f"https://aixec.exbridge.jp/sns.php?id={item.get('id')}" if isinstance(item, dict) and item.get("id") else "",
        "response": parsed,
        "fallback_errors": errors,
    }


def sync_public_json() -> dict[str, Any]:
    return geo.sync_public_json()


def produce_daily_video_job(topic: str = DEFAULT_TOPIC, target_minutes: int = 10, source: str = "worker_auto", force_run: bool = False, **_: Any) -> dict[str, Any]:
    geo.load_env_file(Path(os.environ.get("AIXEC_ENV_FILE", "/home/kojima/work/aixec/.env")))
    profile = select_topic_profile(topic)
    topic = str(profile.get("topic") or topic or DEFAULT_TOPIC)
    if not force_run and os.environ.get("KAGENTREACH_AI_MONETIZATION_FORCE_RUN", "0") != "1":
        state = read_json(STATE_PATH, {"runs": []})
        today = now_jst()[:10]
        for run_item in state.get("runs") or []:
            if str(run_item.get("created_at") or "").startswith(today) and run_item.get("youtube_url"):
                return {"ok": True, "status": "skipped", "items": 0, "created": 0, "reason": "already_published_today", "latest": run_item}
    profile_categories = [str(item) for item in (profile.get("categories") or DEFAULT_COMMONS_CATEGORIES)]
    collect = collect_sources_job(
        target_count=int(os.environ.get("KAGENTREACH_AI_MONETIZATION_CANDIDATE_COUNT", "24")),
        query=str(profile.get("query") or DEFAULT_QUERY),
        categories=profile_categories,
        profile_id=str(profile.get("id") or ""),
    )
    candidates = read_json(CANDIDATES_PATH, [])
    references = [c for c in candidates if c.get("kind") == "youtube_reference" and (not profile.get("id") or c.get("profile_id") == profile.get("id"))]
    if len(references) < 3:
        references = [c for c in candidates if c.get("kind") == "youtube_reference"]
    footage = [c for c in candidates if c.get("kind") == "footage" and (c.get("profile_id") == profile.get("id") or c.get("category") in profile_categories)]
    if len(footage) < 3:
        footage = [c for c in candidates if c.get("kind") == "footage"]
    if len(footage) < 3:
        raise RuntimeError("not enough licensed AI/Web3 footage candidates")
    job_id = slugify(topic + iso_now(), "aimon-video")
    work = WORK_DIR / job_id
    script = generate_script(topic, references, target_minutes=target_minutes, footage=footage, profile=profile)
    video = build_video(topic, script, footage, work, target_minutes=target_minutes)
    write_json(work / "script.json", script)
    sources = read_json(work / "sources.json", [])
    description = "\n".join([
        normalize_space(script.get("summary") or "AI/Web3収益化とOSS実装の長尺解説です。"),
        "",
        "使用素材・出典:",
        *[f"- {line}" for line in sources[:20]],
        "",
        "Kurage Entertainment:",
        f"{KURAGE_BASE}/entertainment.php",
        "",
        "#AI #Codex #ClaudeCode #Web3 #SNS収益化 #OSS #Kurage",
    ])
    upload = upload_youtube(video, normalize_space(script.get("title") or topic), description)
    article = publish_article(topic, script, upload, footage)
    sync = sync_public_json()
    try:
        aixsns = post_aixsns(article)
    except Exception as exc:
        aixsns = {"ok": False, "error": str(exc)[-1000:]}
    state = read_json(STATE_PATH, {"runs": []})
    record = {"job_id": job_id, "profile_id": profile.get("id") or "", "topic": topic, "created_at": now_jst(), "video": str(video), "youtube_url": upload["youtube_url"], "article_url": f"{KURAGE_BASE}/entertainment.php?id={article['slug']}", "aixsns": aixsns, "source": source}
    state.setdefault("runs", []).insert(0, record)
    write_json(STATE_PATH, state)
    return {"ok": True, "status": "ok", "items": 1, "created": 1, "profile_id": profile.get("id") or "", "topic": topic, "collect": collect, "youtube_url": upload["youtube_url"], "article_url": record["article_url"], "aixsns": aixsns, "public_sync": sync, "work_dir": str(work)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Kurage AI/Web3 monetization long-form video worker")
    parser.add_argument("command", choices=["collect", "run"], nargs="?", default="collect")
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--target-minutes", type=int, default=10)
    parser.add_argument("--target-count", type=int, default=24)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force-run", action="store_true")
    args = parser.parse_args()
    profile = select_topic_profile(args.topic)
    if args.command == "collect" or args.dry_run:
        result = collect_sources_job(
            target_count=args.target_count,
            query=str(profile.get("query") or DEFAULT_QUERY),
            categories=[str(item) for item in (profile.get("categories") or DEFAULT_COMMONS_CATEGORIES)],
            profile_id=str(profile.get("id") or ""),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(json.dumps(produce_daily_video_job(topic=args.topic, target_minutes=args.target_minutes, force_run=args.force_run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
