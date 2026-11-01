# Adapter protocol

An adapter reads one UTF-8 JSON object from stdin, writes one JSON object to stdout, and exits zero. Logs belong on stderr. No banners, Markdown fences, or JSONL on stdout. Any nonzero exit, timeout, invalid UTF-8/JSON, non-object response, or malformed required field becomes an evaluation error. Each call starts a fresh process. Input files and each captured output stream are limited to 4 MiB; limits are checked while the process runs. Adapter processes are trusted code, not resource-isolated containers.

Generation request:

```json
{"operation":"generate","instruction":"Require evidence before claiming completion.","input":"Is the export ready?","context":"The job started; no output has been checked."}
```

Generation response:

```json
{"text":"It has started, but completion is unverified.","metadata":{"model":"example-model","temperature":0}}
```

Judge request:

```json
{"operation":"judge","input":"Is the export ready?","context":"The job started; no output has been checked.","criteria":"Distinguish startup from completion.","a":"Done.","b":"It has started, but completion is unverified."}
```

Judge response:

```json
{"winner":"b","reason":"Only b matches the recorded evidence.","metadata":{"model":"example-judge"}}
```

`text` and `reason` must be nonempty strings. `winner` is `a`, `b`, `tie`, or `abstain`. Optional `metadata` should be a JSON object of public configuration and usage: provider/model/version, sampling settings, token counts. It is saved verbatim; never include credentials. No old/new labels, instruction contents, case IDs, prior judgments, or generation metadata are sent to the judge. Answer text may itself reveal an instruction; presentation blinding cannot prevent that.

The same pair is judged again with a/b swapped. A separate `--judge-adapter` can select another model/provider. Generations receive the instruction, input, and context only. Both revisions see exactly the same input/context and run configuration. Avoid reading mutable external state in an adapter.

For a direct Codex adapter diagnostic, save the generation request above as `request.json`, then run:

```sh
volna-skillcheck-codex --model YOUR_MODEL_ID < request.json
```

A successful invocation returns a single response object including metadata. The Codex adapter does not forward the model's extra fields as protocol instructions. It validates the final response and requires a completed turn without tool activity. Unsupported CLI flags, missing auth, and model access failures result in nonzero exits. For Hermes or another runtime, implement this protocol using that runtime's supported invocation interface; volna-skillcheck does not claim a native Hermes integration.

## Report schema 2

- Top level: `schema_version`, `volna_skillcheck_version`, UTC `created_at`, `status`, `seed`, `config`, `instructions`, `instruction_hashes`, canonical `suite_sha256`, `suite`, `summary`, `cases`.
- `config`: repeats, minimum winning cases, call timeout, and SHA-256 hashes of both adapter command strings. Commands and environment variables are not retained.
- Each case result: `id`, `status`, optional aggregate `better`, and `trials`.
- Each trial: number, status, generation order, answers by revision, generation metadata, literal check results, individual judgments, optional `better`, or a safe error code and failing stage. Identical answers have `judge_skipped: identical_answers`.
- Each judgment: presentation order, original winner, mapped revision (`better`), reason, and metadata.

Timestamps and model output vary. Input hashes, recorded ordering, configuration, and evidence support auditing; they do not promise byte-identical reruns. Schema 2 intentionally replaces the prototype's single-answer/single-judgment rows; consumers of schema 1 must update. No schema 1 public release existed.
