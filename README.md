# volna-skillcheck

**Change an agent instruction. Replay recorded tasks. Inspect improvements and regressions.**

volna-skillcheck compares two instruction revisions using identical task inputs and recorded context. A blind judge sees the two answers in both orders. Reports retain the answers, judgments, checks, model metadata, and input hashes—including evidence from failed runs.

Python 3.10+, Linux or macOS. No Python runtime dependencies. MIT licensed.

## Try it offline

Clone the repository and install locally:

```sh
git clone https://github.com/vladzima/volna-skillcheck.git
cd volna-skillcheck
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "python examples/mock_adapter.py" \
  --out reports/demo.json
```

Expected: six candidate wins, two ties, `candidate_improvement`, exit 0. Reverse `--old` and `--new` with a **different output path** to see `regression`, exit 2. The fixture is deliberately hardcoded; this verifies the plumbing, not model quality. Each output path must be new.

Installation provides `volna-skillcheck` and `volna-skillcheck-codex`. The example files live in the checkout and source distribution, not the installed wheel. You can also run `python3 volna_skillcheck.py` without installing.

## Evaluate with Codex

Install and authenticate the official [Codex CLI](https://developers.openai.com/codex/cli/). The adapter is tested with **codex-cli 0.166.0**. Older versions may lack required isolation flags. Specify a model available to your account:

```sh
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-codex --model YOUR_MODEL_ID" \
  --out reports/codex.json
```

This uses your existing Codex login and consumes your provider quota. A trial costs two generations and, if the answers differ, two judge calls. Eight cases cost up to 32 calls; `--repeats 3` raises that to 96. Calls are sequential. There are no automatic retries or automatic instruction changes.

The adapter uses fresh temporary directories, read-only sandboxing, ephemeral sessions, an explicit model and reasoning effort (`high` by default). It replaces Codex's built-in instruction prompt, ignores user config and rules, disables AGENTS.md loading, local skill discovery, integrations, hooks, shell, browser, and other optional tools. Unexpected tool activity fails the evaluation. It uses the CLI's `skip_host_skill_discovery` feature, currently marked experimental: revalidate isolation before upgrading Codex. Host-managed policies and Codex's remaining runtime behavior still apply. This is **not a raw-model API benchmark or a sandbox for hostile adapters**.

Model name, reasoning effort, Codex version, prompt hashes, and token usage are saved per call. CLI transport diagnostics are deliberately not copied into reports. If the adapter fails, first check `codex --version` and `codex login status`; run the adapter directly with a synthetic request from [the protocol documentation](docs/protocol.md) to see its diagnostic code.

To use a separate judge or repeat generations:

```sh
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-codex --model YOUR_MODEL_ID" \
  --judge-adapter "volna-skillcheck-codex --model YOUR_JUDGE_MODEL_ID" \
  --repeats 3 --seed 42 --out reports/repeated.json
```

`--seed` controls generation and presentation order, **not model sampling**. Models, aliases, and providers can change; identical inputs do not guarantee identical answers. Use a pinned model snapshot where supported. The bundled adapter uses a 90-second Codex timeout; the runner defaults to 120 seconds per adapter invocation. When increasing either, keep the runner's timeout above the adapter's, allowing startup time.

## Write cases

A suite is a nonempty JSON array with unique string IDs:

```json
[
  {
    "id": "export-status",
    "input": "Is the export ready?",
    "context": "The job started; no output has been checked.",
    "criteria": "Distinguish starting from completing. Identify the missing check.",
    "checks": {"not_contains": ["Export complete."]}
  }
]
```

`id`, `input`, and `criteria` are required. `context` is an optional string of recorded tool results or other task evidence. `checks` supports `contains` and `not_contains`, lists of **case-sensitive literal substrings**. These checks test the answer text; they do not prove a tool action happened. Neither criteria nor checks are given to the generation adapter. Unknown case fields are rejected to catch misspelled configuration.

The eight included scenarios are synthetic: acknowledgment without completion, verification of the wrong command, startup mistaken for success, ambiguous publication after interruption, evidence lost in a summary, telemetry mistaken for delivery, plus two successful baseline controls. Use a held-out suite representative of your own tasks; don't tune instructions against your entire evaluation set.

## Interpret a run

| Verdict | Exit | Meaning |
| --- | --- | --- |
| `candidate_improvement` | 0 | At least five distinct winning cases by default, no observed losses, uncertainty, failed candidate checks, or errors |
| `incomplete` | 1 | A call failed, an evaluation is unfinished, or a checkpoint is from a running process |
| `regression` | 2 | At least one agreed baseline win, or a candidate check failure where the baseline passed |
| `failed_checks` | 2 | Candidate checks failed, including cases where both revisions failed |
| `inconclusive` | 3 | All ties, judge abstention, swapped disagreement, or inconsistent repeated results |
| `insufficient_data` | 3 | Some candidate wins, fewer than `--min-wins` distinct cases |

Invalid inputs and report I/O failures exit 1; CLI usage errors exit 2; Ctrl+C exits 130 and attempts to save partial evidence. Any nonzero exit should fail a promotion gate. A failed run takes precedence over other verdicts; regression counts and failed checks remain visible in its report. Read them, not just the final verdict.

The default `--min-wins 5` is an explicit **review threshold, not a statistical significance claim**. Repeats never count as extra independent cases. Lowering the threshold is useful for a smoke test, but weakens the evidence required for exit 0. See [evaluation methodology and limitations](docs/methodology.md).

## Reports and privacy

Reports use schema version 2 and contain the exact instructions, case inputs/context, answers, reasons, checks, and optional adapter metadata. This makes a run inspectable; it also makes a report sensitive. Reports are created with owner-only permissions and checkpointed atomically after successful calls. Existing files are never overwritten by a new run. Ctrl+C preserves completed evidence; a hard kill leaves the last checkpoint marked `running`. There is no resume mode; use a new report path for another run.

Only use synthetic or sanitized data in public suites. Instructions and case data go to the configured adapter/provider. Adapter commands run with your account permissions and inherit your environment; trust the executable. volna-skillcheck invokes commands directly without a shell. Keep credentials in environment variables or your provider's credential store, never in command arguments or metadata. Commands are recorded as hashes, not plaintext. volna-skillcheck does not redact secrets echoed by models. It has no built-in telemetry.

## Development

```sh
python3 -m unittest discover -s tests -v
python -m pip install build twine
python -m build
python -m twine check dist/*
```

Tests cover the evaluation policy, malformed responses, timeouts and descendant cleanup, interrupted evidence, secure atomic reporting, forward/reverse/tie CLI runs, and a fake Codex executable. CI tests Linux and macOS and installs the built wheel outside the source tree. Real provider tests require credentials and are manual; CI does not spend provider quota.

See [contributing](CONTRIBUTING.md), [adapter protocol](docs/protocol.md), [security](SECURITY.md), and [release checklist](docs/releasing.md).
