from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


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
