# Changelog

## 0.3.0 — 2026-11-01

- Add the portable `volna-skillcheck` agent skill with five-case defaults, existing-provider selection, bounded evaluation, and evidence review.
- Document installation through `npx skills` for OpenCode, Codex, Claude Code, and other compatible harnesses, plus manual installation.
- Add PyPI Trusted Publishing from tagged GitHub releases, with separate build and publish jobs and no stored publishing token.
- Put PyPI and skill installation first in the README; use absolute documentation links for the PyPI project page.

## 0.2.0 — 2026-11-01

- Add OpenCode V2, Claude Code, and OpenAI-compatible Chat Completions adapters.
- Share the generation/judge prompts and response validation across bundled adapters.
- Validate API responses, refuse credential-bearing redirects, and support local endpoints.
- Rewrite the README around a quick start and provider choice; add agent workflows, an OpenCode command template, and a manual CI example.
- OpenCode is live-tested; Claude Code is fixture-tested and hosted API compatibility remains unverified.

## 0.1.0 — 2026-11-01

- Installable Python CLI and authenticated Codex CLI adapter; no Python runtime dependencies.
- Swapped blind judgments, explicit abstention, repeated trials, distinct-case evidence threshold, and literal answer checks.
- Schema 2 reports with input provenance, model metadata, incremental atomic checkpoints, and private file permissions.
- Strict suite validation, bounded adapter output, process-group timeouts, and interruption handling.
- Eight synthetic scenarios with baseline success controls, offline tests, CI, and MIT licensing.

The original unversioned prototype used schema 1. No compatibility with its report rows is promised.
