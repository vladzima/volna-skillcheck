# Cases, reports, and CLI behavior

## Case fields

A suite is a nonempty JSON array with unique string IDs. Each case requires nonempty `id`, `input`, and `criteria` strings. Optional `context` is a string containing recorded evidence, such as tool results. Unknown fields are rejected so misspelled configuration cannot silently do nothing.

Optional literal checks:

```json
{
  "id": "simple-answer",
  "input": "What is 7 + 5?",
  "criteria": "Answer directly without unnecessary verification demands.",
  "checks": {"contains": ["12"], "not_contains": ["I cannot answer"]}
}
```

`contains` and `not_contains` are lists of **case-sensitive literal substrings**. Use them only for requirements you can express this way. They do not establish whether an action happened. Criteria and checks are withheld from generation calls. A candidate failing checks cannot earn a positive overall verdict even when the judge prefers it.

## Exit codes

| Verdict | Exit | Meaning |
| --- | --- | --- |
| `candidate_improvement` | 0 | At least `--min-wins` distinct wins, with no observed losses, errors, uncertainty, or failed candidate checks |
| `incomplete` | 1 | A call failed or the run is unfinished |
| `regression` | 2 | An agreed baseline win, or a candidate check failure where the baseline passed |
| `failed_checks` | 2 | Candidate checks failed, including cases where both revisions failed |
| `inconclusive` | 3 | All ties, abstention, swapped disagreement, or inconsistent repeated results |
| `insufficient_data` | 3 | Some candidate wins, fewer than the required distinct cases |

Input/report I/O errors exit 1; CLI usage errors exit 2; Ctrl+C exits 130 and attempts to preserve partial evidence. Treat every nonzero exit as a failed promotion gate. Errors take precedence over verdicts, but established regression counts and failed checks remain visible in the report.

`--min-wins` defaults to 5. It is a review threshold, not a statistical guarantee. Don't lower it just to obtain a passing result. `--repeats` repeats generations within each case; repeats do not create independent evidence.

## Reports

Schema 2 contains the exact instructions and suite, their hashes, the evaluation configuration, all generated answers, literal checks, judge explanations, model metadata, and safe error codes. See the [protocol guide](protocol.md) for the field layout.

Reports are created with owner-only permissions and atomically checkpointed after successful calls. A new run refuses to overwrite any existing file, including its inputs. Ctrl+C keeps completed evidence; a hard kill leaves the most recent checkpoint marked `running`. There is no resume mode—rerun with a new report path.

Input files and each captured adapter output stream are limited to 4 MiB. The API adapter also limits its response body. Timeouts terminate ordinary adapter process groups; these safeguards do not contain a malicious executable that escapes its process group.

## Reproducibility and cost

`--seed` controls generation/presentation order, **not model sampling**. Model snapshots, runtime versions, provider settings, and input hashes help audit a result, but reruns need not be identical. Adapters record available usage and model settings; not every provider reports monetary cost.

Budget up to four model calls per case per repeat. Identical answers skip judging. There are no automatic paid retries. A CLI/runtime can make its own internal calls, so this is an adapter-call estimate, not an exact billing guarantee.

## Development checks

```sh
python3 -m unittest discover -s tests -v
python -m pip install build twine
python -m build
python -m twine check dist/*
```

The offline suite uses subprocess fixtures and a loopback HTTP server. Restricted environments must permit local socket creation for the API tests. Live model checks are separate and use sanitized cases.
