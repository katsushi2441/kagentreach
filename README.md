# Kurage Agent Reach

Kurage Agent Reach is an AI-powered research engine for discovering monetizable trends, reference videos, OSS projects, and social signals for Kurage content automation.

This repository owns the reusable information-collection layer used by Kurage-related products. It is intentionally separate from individual products such as kvtuber, kargov, kmontage, and kurage_web.

## Scope

- Web and semantic search for source discovery
- YouTube reference video discovery
- X/Twitter research through authenticated browser sessions
- OSS and GitHub project research
- Trend and monetization-signal collection for content pipelines

## External Tools

`Agent-Reach/` may exist locally as an upstream OSS clone, but it is not part of this repository. Keep upstream OSS, browser profiles, cookies, and secrets outside Git.

## X Search With Browser-Use

Use the helper below to search X without extracting or printing cookies. It reuses the authenticated Chrome profile used by browser-use.

```bash
/home/kojima/work/browser_agent/.venv/bin/python \
  scripts/x-search-browser-use.py \
  'Claude Code make money SaaS' -n 5 --mode top
```

The helper saves/prints summarized search results. If browser-use cannot return strict JSON, the raw result is preserved so downstream jobs can still inspect it.

## Daily Monetization Video Digest

`scripts/monetization_daily.py` runs the application-specific workflow. In
production, kdeck owns the schedule and enqueues
`kagentreach_jobs.run_daily_digest_job` through rqdb4ai.

1. Search overseas long-form YouTube videos around Web3, Codex, Claude Code, vibe coding, SNS, AI, and monetization.
2. Collect supporting web sources through `mcporter` + Exa when available.
3. Send the best unused video to Kurage Montage.
4. Create an AI OSS technical article under `vwork/articles/`.
5. Include both the original reference video and the generated Kurage video URL.
6. Cross-post by email to Hatena/Blogger and announce on AIxSNS.

Dry run:

```bash
python3 scripts/monetization_daily.py --dry-run
```

Full run:

```bash
python3 scripts/monetization_daily.py
```

RQDB4AI entrypoint:

```text
kagentreach_jobs.run_daily_digest_job
```

Do not run this workflow from a standalone cron/systemd timer in production.
Use kdeck Goal Queue so scheduling, cooldown, daily target, and job status stay
visible in the shared controller.

### vwork Git Discipline

The daily digest writes articles into `/home/kojima/work/vwork`. The worker must
never leave generated articles uncommitted:

- before expensive generation, verify `vwork` is clean and rebase from
  `origin/main`
- if `vwork` already has unrelated uncommitted changes, stop before generating
  a Kurage video
- after writing the article, commit the generated article and `articles.md`
  before any further pull/rebase
- after push, verify `vwork` is clean

## Geopolitics / War OSINT Video

Geopolitics and war OSINT video publishing also runs through the shared
kagentreach -> kdeck -> rqdb4ai pattern.

RQDB4AI entrypoints:

```text
kagentreach_jobs.collect_geopolitics_osint_sources_job
kagentreach_jobs.run_geopolitics_osint_video_job
```

Responsibilities:

- kagentreach owns the research-layer entrypoint and query/collection control
- kdeck owns the daily goal, duplicate guard, cooldown, and status visibility
- rqdb4ai owns queue execution
- kurage_web still owns entertainment.php data files, YouTube upload, and
  published article registration

Do not run the old `kurage-geopolitics-video.timer` in production; the kdeck
Goal Queue should be the only scheduler.
