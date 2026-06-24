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
