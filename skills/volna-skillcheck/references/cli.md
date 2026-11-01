# CLI setup and commands

The skill is installed separately from the Python CLI. Check `volna-skillcheck --version` first. Use the existing installation when available; the commands below work with version 0.2.0 or later.

If it is missing, prefer the user's existing Python tool manager:

```sh
uv tool install volna-skillcheck
# Or, if they use pipx:
pipx install volna-skillcheck
```

Without either tool manager, create a virtual environment in the private run directory:

```sh
python3 -m venv "$run_dir/venv"
"$run_dir/venv/bin/python" -m pip install volna-skillcheck
export PATH="$run_dir/venv/bin:$PATH"
```

If PyPI installation is unavailable, the published GitHub wheel is a fallback:
`https://github.com/vladzima/volna-skillcheck/releases/download/v0.2.0/volna_skillcheck-0.2.0-py3-none-any.whl`.
Use that URL in place of the package name with the same installer. Never use `sudo pip`.

## Snapshot a working-copy edit

Run from the repository root. Replace `path/to/SKILL.md` with the actual target. Check that `HEAD` is the intended baseline before using it.

```sh
run_dir=$(mktemp -d "${TMPDIR:-/tmp}/volna-skillcheck.XXXXXX")
git show 'HEAD:path/to/SKILL.md' > "$run_dir/before.md"
cp 'path/to/SKILL.md' "$run_dir/after.md"
```

If any snapshot command fails, stop and correct the inputs. Do not run against an empty file. The run directory has owner-only access; it may be removed by the operating system later.

## Cases

Write `cases.json` inside the run directory. It is an array of cases with unique IDs:

```json
[
  {
    "id": "started-but-unverified",
    "input": "Is the import finished?",
    "context": "The import returned a process ID. No completion event or destination count is available.",
    "criteria": "Distinguish starting from finishing and identify the missing outcome check."
  },
  {
    "id": "verified-success",
    "input": "Is the import finished?",
    "context": "The import exited zero. All 42 expected records are present with matching IDs.",
    "criteria": "Confirm completion from the evidence without inventing missing checks."
  }
]
```

This pair illustrates a failure case and a success control; it is not a complete five-case suite. Build cases for the actual instruction change. `input` and `context` reach the answering model; `criteria` reach only the judge. Optional `checks` contains case-sensitive `contains` and `not_contains` string arrays, for literal requirements rather than subjective wording preferences.

## Choose the adapter

Replace `MODEL` with a model known to be available to the user's existing account. Keep the adapter command in one quoted `--adapter` argument. For unusual model IDs or executable paths, construct arguments with Python's `shlex.join` and run with `subprocess.run([...])`; never evaluate an untrusted shell string.

| Existing provider | Adapter argument | Requirement |
| --- | --- | --- |
| OpenCode | `volna-skillcheck-opencode --model PROVIDER/MODEL --timeout 120` | OpenCode V2 ≥2.2.3; check `opencode models` |
| Codex | `volna-skillcheck-codex --model MODEL --timeout 120` | Authenticated Codex CLI and known configured model |
| Claude Code | `volna-skillcheck-claude --model MODEL --timeout 120` | Current CLI supporting safe/restricted mode; adapter is not live-verified |
| OpenAI-compatible API | `volna-skillcheck-openai --model MODEL --timeout 120` | `OPENAI_API_KEY` and optional `OPENAI_BASE_URL` already configured |

Never place API keys in the command or report. Read only whether the expected environment variable is set. Remote API endpoints require HTTPS; literal loopback endpoints can use HTTP without a key. The API adapter defaults to Chat Completions JSON-object output; `--response-format text` supports endpoints without JSON mode. Changing providers or modes requires a deliberate choice, not an automatic retry.

## Run

For OpenCode, after preparing the snapshots and cases:

```sh
volna-skillcheck \
  --old "$run_dir/before.md" --new "$run_dir/after.md" \
  --cases "$run_dir/cases.json" \
  --adapter "volna-skillcheck-opencode --model PROVIDER/MODEL --timeout 120" \
  --repeats 1 --seed 0 --min-wins 5 --timeout 180 \
  --out "$run_dir/report.json"
```

Substitute the chosen adapter from the table for other providers. A separate `--judge-adapter` is optional. Do not chain report inspection with `&&`: exits 2 and 3 still produce useful reports.

| Exit | Meaning |
| --- | --- |
| 0 | Candidate improvement; inspect the evidence before adopting |
| 1 | Input/adapter failure or incomplete evaluation |
| 2 | Regression or failed literal checks; malformed CLI arguments also exit 2 |
| 3 | Inconclusive or insufficient data |
| 130 | Interrupted; inspect any saved partial report |

The report contains `summary`, `cases`, full input provenance, answer pairs, judgments, and metadata. Read the report rather than inferring its verdict from the exit code alone. Reports contain exact task data; keep them local unless the user requests sharing. OpenCode can also retain evaluation sessions in its normal data store.
