# volna-skillcheck

### Did that new agent rule actually help?

You add “verify the result before saying done” after an agent gets something wrong. It sounds sensible—but does it fix the failure? Does it make the agent needlessly hesitant on tasks it already handled well?

**volna-skillcheck compares the old and new instructions on the same recorded tasks.** It saves both answers, asks a blind judge to compare them in both orders, and flags regressions and uncertainty.

Use it before changing a `SKILL.md`, `AGENTS.md`, `CLAUDE.md`, or an agent's system prompt.

[Quick start](#quick-start) · [Choose an adapter](#choose-an-adapter) · [Use it with your agent](docs/workflows.md) · [How judging works](docs/methodology.md)

Python 3.10+ · Linux and macOS · MIT · No Python runtime dependencies

## Quick start

**1. Install from the repository.**

```sh
git clone https://github.com/vladzima/volna-skillcheck.git
cd volna-skillcheck
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

**2. Try the offline example.** No account or API key needed.

```sh
volna-skillcheck \
  --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "python examples/mock_adapter.py" \
  --out reports/demo.json
```

The fixture produces **6 wins, 2 ties, and no regressions**. Swap `--old` and `--new` and use a new output path to see a regression. This is a hardcoded demo of the tool, not evidence of model quality.

## Choose an adapter

Keep the same command and replace `--adapter`:

| Run through | Adapter command | Setup / verification |
| --- | --- | --- |
| **OpenCode** | `volna-skillcheck-opencode --model PROVIDER/MODEL` | Existing login; requires V2 ≥2.2.3; live-tested on 2.2.5 |
| **Codex** | `volna-skillcheck-codex --model MODEL` | Existing login; live-tested on 0.166.0 |
| **OpenAI-compatible API** | `volna-skillcheck-openai --model MODEL` | `OPENAI_API_KEY`; configurable endpoint; tested with a local HTTP server |
| **Claude Code** | `volna-skillcheck-claude --model MODEL` | Existing installation/login; fixture-tested, **not live-verified** |

For example, with an OpenCode model available in `opencode models`:

```sh
volna-skillcheck \
  --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-opencode --model openai/gpt-6-astra#high" \
  --out reports/opencode.json
```

The example model must be available to your account. See the [adapter setup guide](docs/adapters.md) for API endpoints, Claude requirements, separate judge models, timeouts, and isolation details.

## Try your own instruction change

You need three things:

1. **The old and new instructions** as two text files.
2. **A few representative tasks**, with the evidence the agent had at the time.
3. **A criterion** describing what a good answer should do.

A case looks like this:

```json
[
  {
    "id": "export-status",
    "input": "Is the export ready?",
    "context": "The job started, but nobody has checked the output file.",
    "criteria": "Distinguish starting from completing. Say what still needs checking."
  }
]
```

Save it as `cases.json` and pass it to `--cases`. Add cases where the old instruction already worked, too. A single case can expose a regression; it cannot meet the default five-win improvement threshold.

**Want a ready-to-copy workflow?** The [agent integration guide](docs/workflows.md) walks through testing an `AGENTS.md` edit, a skill revision, an OpenCode `/skillcheck` command, and a manual CI evaluation with a provider key.

## Read the result

The CLI prints a summary. Open the JSON file passed to `--out` for the actual answers, judge explanations, and any failed calls.

| Result | What to do | Exit |
| --- | --- | --- |
| `candidate_improvement` | Review the winning answers before adopting the change | 0 |
| `regression` / `failed_checks` | Inspect what got worse or failed a required check | 2 |
| `inconclusive` / `insufficient_data` | Inspect disagreement or add representative cases | 3 |
| `incomplete` | Fix the adapter/input problem and rerun to a new report path | 1 |

By default, a candidate needs **five distinct winning cases**, no observed losses, no uncertainty, and no failed checks. Five wins is a review threshold, not statistical significance. Repeated trials don't count as additional independent cases.

Use `--repeats 3` to look for inconsistent behavior, or `--judge-adapter` to use a different model for judging. Each trial costs up to **four model calls per case**. Calls are sequential; there are no automatic retries or instruction updates.

> **What this measures:** answers produced from recorded context. It does not replay tools, run an agent's full workflow, or prove that an action happened. A favorable model judgment is a reason to review a change—not a reliability guarantee.

## Keep your data private

Use synthetic or sanitized cases. Instructions and case data go to your selected adapter/provider. Reports contain the exact inputs, answers, and reasons. They are created with owner-only permissions; this repository ignores `reports/`. Each run needs a fresh output path, and partial evidence is saved as the run progresses.

Adapters are trusted local executables, not a sandbox for hostile code. Provider and CLI logging policies still apply; OpenCode may retain evaluation sessions in its local store. [Security details](SECURITY.md).

## More detail

- [Adapter setup](docs/adapters.md) — OpenCode, Codex, Claude Code, and compatible APIs
- [Agent workflows](docs/workflows.md) — examples you can put into an existing project
- [Cases and reports](docs/usage.md) — literal checks, exit codes, errors, and reproducibility
- [Methodology](docs/methodology.md) — judgment policy and limitations
- [Adapter protocol](docs/protocol.md) — connect another runtime
- [Contributing](CONTRIBUTING.md) — development and tests

Run the offline suite with `python3 -m unittest discover -s tests -v`. Python package artifacts are available from [GitHub Releases](https://github.com/vladzima/volna-skillcheck/releases); the project is not published on PyPI.
