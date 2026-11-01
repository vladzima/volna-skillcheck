# Install the skill

The `volna-skillcheck` skill teaches your existing agent to prepare cases, compare instruction revisions, and explain regressions. It is a portable `SKILL.md` with a supporting CLI guide, not a background service or a new agent runtime.

## Two installs, then a plain-language request

Install the Python CLI once:

```sh
uv tool install volna-skillcheck
# Or: pipx install volna-skillcheck
```

Then use the [skills installer](https://github.com/vercel-labs/skills) to install the instructions into your harness:

```sh
npx skills add vladzima/volna-skillcheck --skill volna-skillcheck
```

Choose your harness when prompted. This requires Node.js 22.20+ and installs into the current project by default. Add `-g` for all projects. The skill can also guide CLI installation if you start with the skill alone. An existing version 0.2.0+ of the CLI works.

To select the harness explicitly:

```sh
# OpenCode, all projects
npx skills add vladzima/volna-skillcheck --skill volna-skillcheck -a opencode -g

# Codex, all projects
npx skills add vladzima/volna-skillcheck --skill volna-skillcheck -a codex -g

# Claude Code, all projects
npx skills add vladzima/volna-skillcheck --skill volna-skillcheck -a claude-code -g
```

These commands install skill files, not the harness applications. To pin the skill to this release, replace `vladzima/volna-skillcheck` with `https://github.com/vladzima/volna-skillcheck/tree/v0.3.0/skills/volna-skillcheck`.

Open a new agent session so the installed skill is discovered. Ask:

> Use volna-skillcheck to compare my skill edit with the previous version. Use my current provider and model. Show the evidence for improvements or regressions.

Explicit invocation is `@volna-skillcheck` in [OpenCode V2](https://dev.opencode.ai/v2/docs/skills/), `$volna-skillcheck` in Codex, and `/volna-skillcheck` in [Claude Code](https://code.claude.com/docs/en/skills).

## Defaults

| Choice | Default |
| --- | --- |
| Baseline | Last committed target file; if the edit is already committed, the preceding differing revision |
| Candidate | Current file, preserved without changes |
| Cases | Five representative sanitized tasks, including at least two successful baseline controls |
| Provider/model | Existing user selection, otherwise the current harness's known authenticated model; ask if unknown |
| Trials | One per case, seed 0, five distinct wins required |
| Budget | Up to 20 adapter calls for five cases; announce before starting |
| Timeouts | 120 seconds per adapter, 180 seconds at the runner |
| Data | A fresh private temporary directory outside the repository, or the user's chosen ignored location |
| Adoption | Review evidence; no automatic edits, retries, commits, or publishing |

Explicit user choices override defaults. Existing representative suites are reused; a larger suite needs an explicit larger budget or a disclosed subset. The agent prepares a bounded comparison, waits for completion, and reports the actual verdict and saved report path. Temporary directories can be removed by the OS; request a durable ignored directory if you need to keep the evidence.

Five cases are an initial check, not a benchmark. Newly generated cases are exploratory, same-model judging can be biased, and the tool tests answers from recorded evidence rather than live tool execution. Use held-out tasks and repeated trials deliberately for stronger evidence.

## Manual installation without Node.js

Clone the repository and copy the **entire** `skills/volna-skillcheck/` directory, including `references/` and `agents/`, into your harness's skill directory:

| Harness | Global directory |
| --- | --- |
| OpenCode | `~/.config/opencode/skills/` |
| Codex | `~/.agents/skills/` |
| Claude Code | `~/.claude/skills/` |

For example, for OpenCode:

```sh
git clone https://github.com/vladzima/volna-skillcheck.git
mkdir -p ~/.config/opencode/skills
cp -R volna-skillcheck/skills/volna-skillcheck ~/.config/opencode/skills/
```

Inspect an existing installation before copying over it. For other harnesses, use their documented Agent Skills directory. The skill and its relative reference work without the original repository checkout; the Python wheel supplies the CLI separately, and the source archive includes the skill files.

## Check installation

`volna-skillcheck --version` verifies that the executable is on your shell's `PATH`. `npx skills list -g` lists global skill installs (`npx skills list` for project installs). In a new agent session, ask it to load `volna-skillcheck` and summarize its defaults without starting an evaluation. If it finds the skill but cannot run the CLI, fix the agent process's `PATH` or activate the CLI virtual environment before launching it.

Installing the skill does not configure API keys or log in to a provider. The [adapter guide](adapters.md) describes supported versions, credentials, and verification limits; the [manual workflows](workflows.md) remain available if you prefer explicit CLI commands.

Installation and bundled references have been checked with the skills installer for OpenCode, Codex, and Claude Code. Live skill invocation remains unverified: the development machine's OpenCode 2.2.5 returned an empty skill registry, including under its normal configuration. The OpenCode **CLI adapter** has been live-tested separately; skill discovery is a different integration point.
