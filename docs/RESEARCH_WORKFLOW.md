# Research Workflow

Kurage Agent Reach collects source candidates before content generation. A typical workflow is:

1. Search YouTube for reference videos with `yt-dlp`.
2. Search the open web with `mcporter` and Exa for supporting articles and source validation.
3. Search X through `scripts/x-search-browser-use.py` when social signals or viral hooks are useful.
4. Store only public URLs, summaries, and metadata in downstream product data.
5. Do not store cookies, browser profile data, OAuth tokens, or upstream OSS source code in this repository.

For Claude Code / Codex / Web3 monetization content, useful query patterns include:

- `Claude Code make money SaaS`
- `Claude Code build sell SaaS`
- `vibe coding make money app`
- `Codex Claude Code developer agency`
- `Web3 AI agent crypto automation`

## Daily Monetization Digest

The daily monetization digest app logic is implemented in:

```text
scripts/monetization_daily.py
```

The rqdb4ai job entrypoint is:

```text
kagentreach_jobs.run_daily_digest_job
```

It intentionally keeps the discovery layer in `kagentreach` and delegates:

- reference-video summarization to `kmontage`
- video rendering to Kurage
- article storage to `vwork/articles`
- email cross-posting to the existing SMTP configuration in `/home/kojima/work/aixec/.env`
- announcement publishing to AIxSNS

Production scheduling belongs to kdeck Goal Queue, not to a standalone
cron/systemd timer. kdeck enforces daily targets, cooldowns, duplicate-running
guards, and rqdb4ai job visibility.

Runtime state is stored under `data/` and is ignored by Git so the worker can
remember already-used source videos without polluting the repository.
