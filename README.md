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
