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

## AI/Web3 Monetization Long-Form Video

The former daily war/geopolitics long-form video slot is replaced by an
AI/Web3/Codex/Claude Code/SNS monetization long-form workflow.

RQDB4AI entrypoint:

```text
kagentreach_jobs.run_ai_monetization_longform_video_job
```

Responsibilities:

- kagentreach owns topic rotation, YouTube trend/reference discovery, and the
  application entrypoint
- kdeck owns the once-a-day goal, cooldown, duplicate guard, and status
  visibility
- rqdb4ai owns queue execution on `kurage-video-worker`
- kurage_web owns entertainment.php article data, YouTube upload, and public
  JSON sync

Content rule:

- The production YouTube upload path still uses license-explicit footage by
  default. Do not silently upload a video built from unreviewed third-party
  YouTube excerpts.
- The review path is `test-kurage`: it may use visual excerpts from the
  source YouTube video, pages from a source PDF, or screenshots from a source
  blog/article so the result can be checked on `kuragev.php` before any public
  YouTube upload decision.
- A one-hour-plus viral YouTube video compressed into a 10-minute explainer is
  one valid pattern, not a hard requirement. The hard requirement is faithful
  source analysis with relevant real/screen/document visuals.
- Reference-visual generation must fail loudly if it cannot use the specified
  YouTube/PDF/blog source. Do not fall back to unrelated stock/Wikimedia footage and
  pretend it reflects the reference.
- Narration must be faithful to the reference source: concrete takeaways,
  numbers, steps, risks, and monetization logic. Do not drift into
  war/geopolitics/OSINT, generic AI hype, or repeated filler.
- Production notes, license caveats, URL spelling, and raw English titles belong
  in metadata, not in the spoken script.
- If the script becomes thin, generic, repetitive, or mostly production notes,
  reject it and regenerate/fail instead of producing an "inchiki" video.

Kurage review generation from a specific source URL:

```bash
python3 scripts/ai_monetization_longform_video.py test-kurage \
  --force-url 'https://www.youtube.com/watch?v=...' \
  --target-minutes 10
```

RQDB4AI review entrypoint:

```text
kagentreach_jobs.run_ai_monetization_reference_kurage_test_job
```

Dry run / source collection:

```bash
python3 scripts/ai_monetization_longform_video.py --dry-run
```

Full production run after review approval:

```bash
python3 scripts/ai_monetization_longform_video.py run
```

## Geopolitics / War OSINT Video

Geopolitics and war OSINT video publishing is kept as a disabled reference. The
daily production slot should use the AI/Web3 monetization long-form workflow
above unless the content strategy explicitly returns to geopolitics.

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

Script quality rule:

- The narration must explain the geopolitical/OSINT topic itself. Do not put
  production notes, license disclaimers, YouTube reused-content warnings,
  violence-policy caveats, or footage-handling instructions into the spoken
  script. Those notes belong in metadata, source lists, or article safety notes,
  not in the video narration.
- If the generated narration becomes mostly production notes after cleanup, the
  worker must reject it and regenerate/fallback to a real explainer script.

Do not run the old `kurage-geopolitics-video.timer` in production; the kdeck
Goal Queue should be the only scheduler.
