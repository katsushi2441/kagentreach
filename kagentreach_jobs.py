from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
KURAGE_WEB_BACKEND = Path(os.environ.get("KURAGE_WEB_BACKEND", "/home/kojima/work/kurage_web/backend"))


def _last_json(stdout: str) -> dict[str, Any]:
    lines = [line for line in stdout.splitlines() if line.strip()]
    for start in range(len(lines)):
        chunk = "\n".join(lines[start:])
        try:
            value = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return {"stdout": stdout[-4000:]}


def run_daily_digest_job(dry_run: bool = False, **kwargs: Any) -> dict[str, Any]:
    """RQDB4AI entrypoint for the daily monetization video digest.

    kdeck owns scheduling and enqueues this function through rqdb4ai. The actual
    app-specific pipeline remains in scripts/monetization_daily.py.
    """
    cmd = [sys.executable, str(ROOT / "scripts" / "monetization_daily.py")]
    if dry_run:
        cmd.append("--dry-run")
    if kwargs.get("force_url"):
        cmd.extend(["--force-url", str(kwargs["force_url"])])
    if kwargs.get("limit_per_query"):
        cmd.extend(["--limit-per-query", str(int(kwargs["limit_per_query"]))])

    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=int(kwargs.get("timeout_seconds") or 7200))
    parsed = _last_json(proc.stdout)
    ok = proc.returncode == 0 and bool(parsed.get("ok", dry_run))
    result: dict[str, Any] = {
        "ok": ok,
        "created": 1 if ok and not dry_run else 0,
        "items": 1 if ok and not dry_run else 0,
        "dry_run": dry_run,
        "source": str(kwargs.get("source") or "rqdb4ai"),
        "returncode": proc.returncode,
        "result": parsed,
    }
    if proc.stderr.strip():
        result["stderr"] = proc.stderr[-4000:]
    if not ok:
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    return result


def run_ai_monetization_longform_video_job(
    dry_run: bool = False,
    topic: str = "",
    target_minutes: int = 10,
    force_run: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """RQDB4AI entrypoint for the AI/Web3 monetization long-form YouTube video.

    This is the replacement path for the former war/geopolitics OSINT daily
    long-form slot. kagentreach owns the topic/research entrypoint, kdeck owns
    schedule/cooldown, rqdb4ai owns execution, and kurage_web owns the public
    entertainment.php data.
    """
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "ai_monetization_longform_video.py"),
        "run",
        "--target-minutes",
        str(int(target_minutes or kwargs.get("target_minutes") or 10)),
    ]
    if topic or kwargs.get("topic"):
        cmd.extend(["--topic", str(topic or kwargs.get("topic"))])
    if dry_run:
        cmd.append("--dry-run")
    if force_run:
        cmd.append("--force-run")
    if kwargs.get("target_count"):
        cmd.extend(["--target-count", str(int(kwargs["target_count"]))])

    proc = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, timeout=int(kwargs.get("timeout_seconds") or 7200))
    parsed = _last_json(proc.stdout)
    ok = proc.returncode == 0 and bool(parsed.get("ok", dry_run))
    already_done = str(parsed.get("status") or "") == "skipped" and str(parsed.get("reason") or "") == "already_published_today"
    items = int(parsed.get("items") or parsed.get("created") or 0)
    if already_done:
        items = 1
    wrapped: dict[str, Any] = {
        "ok": ok,
        "status": parsed.get("status") or ("ok" if ok else "error"),
        "items": items,
        "created": items,
        "dry_run": dry_run,
        "source": str(kwargs.get("source") or "rqdb4ai"),
        "returncode": proc.returncode,
        "youtube_url": parsed.get("youtube_url") or "",
        "article_url": parsed.get("article_url") or "",
        "result": parsed,
    }
    if proc.stderr.strip():
        wrapped["stderr"] = proc.stderr[-4000:]
    if not ok:
        raise RuntimeError(json.dumps(wrapped, ensure_ascii=False))
    return wrapped


def _load_kurage_geopolitics_module() -> Any:
    if str(KURAGE_WEB_BACKEND) not in sys.path:
        sys.path.insert(0, str(KURAGE_WEB_BACKEND))
    import geopolitics_video_jobs  # type: ignore

    return geopolitics_video_jobs


def collect_geopolitics_osint_sources_job(
    target_count: int = 24,
    query: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Collect OSINT reference/footage candidates through kagentreach.

    The underlying media registry remains in kurage_web because entertainment.php
    owns the published data files. kdeck/rqdb4ai call this kagentreach entrypoint
    so discovery is controlled from the shared research layer.
    """
    module = _load_kurage_geopolitics_module()
    result = module.collect_sources_job(
        target_count=int(target_count or kwargs.get("target_count") or 24),
        query=query or kwargs.get("query") or module.DEFAULT_QUERY,
        source=str(kwargs.get("source") or "rqdb4ai"),
    )
    return {
        "ok": bool(result.get("ok", True)),
        "status": result.get("status") or "ok",
        "items": int(result.get("items") or result.get("created") or 0),
        "created": int(result.get("created") or result.get("items") or 0),
        "source": str(kwargs.get("source") or "rqdb4ai"),
        "result": result,
    }


def run_geopolitics_osint_video_job(
    dry_run: bool = False,
    topic: str = "",
    target_minutes: int = 10,
    force_run: bool = False,
    **kwargs: Any,
) -> dict[str, Any]:
    """RQDB4AI entrypoint for the daily geopolitics/war OSINT YouTube video.

    kagentreach owns the research-layer entrypoint, kdeck owns schedule/cooldown,
    rqdb4ai owns execution, and kurage_web owns publishing data for
    entertainment.php.
    """
    module = _load_kurage_geopolitics_module()
    topic = topic or str(kwargs.get("topic") or module.DEFAULT_TOPIC)
    target_minutes = int(target_minutes or kwargs.get("target_minutes") or 10)
    if dry_run:
        return collect_geopolitics_osint_sources_job(
            target_count=int(kwargs.get("target_count") or os.environ.get("KURAGE_GEOPOLITICS_CANDIDATE_COUNT", "24")),
            query=str(kwargs.get("query") or module.DEFAULT_QUERY),
            source=str(kwargs.get("source") or "rqdb4ai"),
        )
    old_force = os.environ.get("KURAGE_GEOPOLITICS_FORCE_RUN")
    if force_run:
        os.environ["KURAGE_GEOPOLITICS_FORCE_RUN"] = "1"
    try:
        result = module.produce_daily_video_job(
            topic=topic,
            target_minutes=target_minutes,
            source=str(kwargs.get("source") or "rqdb4ai"),
        )
    finally:
        if force_run:
            if old_force is None:
                os.environ.pop("KURAGE_GEOPOLITICS_FORCE_RUN", None)
            else:
                os.environ["KURAGE_GEOPOLITICS_FORCE_RUN"] = old_force
    ok = bool(result.get("ok"))
    already_done = str(result.get("status") or "") == "skipped" and str(result.get("reason") or "") == "already_published_today"
    items = int(result.get("items") or result.get("created") or 0)
    if already_done:
        items = 1
    wrapped = {
        "ok": ok,
        "status": result.get("status") or ("ok" if ok else "error"),
        "items": items,
        "created": items,
        "source": str(kwargs.get("source") or "rqdb4ai"),
        "youtube_url": result.get("youtube_url") or "",
        "article_url": result.get("article_url") or "",
        "result": result,
    }
    if not ok:
        raise RuntimeError(json.dumps(wrapped, ensure_ascii=False))
    return wrapped
