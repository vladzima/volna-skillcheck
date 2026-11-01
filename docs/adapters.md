# Adapter setup

An adapter supplies model answers and blind judgments. All bundled adapters use the same prompt and response contract; the runner handles comparison and reporting. Installing volna-skillcheck installs the Python commands below, **not** the third-party CLIs.

Choose an explicit model supported by your provider. Existing login state is reused; no credentials belong in adapter arguments or reports. Runtime behavior differs between providers, so compare instruction revisions with the same generation adapter and model.

## OpenCode

Requires **OpenCode V2, version 2.2.3 or newer within V2**. Live-tested with 2.2.5. V1 and unknown major versions are rejected because the isolation policies differ.

```sh
opencode auth list
opencode models

volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-opencode --model openai/gpt-6-astra#high" \
  --out reports/opencode.json
```

Use any `provider/model` (optionally `#variant`) available to your account. The example uses an existing OpenAI login; other connected built-in providers can be selected the same way.

Each invocation starts a private server with `--standalone`, a fresh working directory, and temporary global configuration. It selects a dedicated agent with the evaluation prompt, denies tools, skills, MCP, and external plugins, disables project instructions and sharing, and strips inherited OpenCode config/server overrides. Provider credentials remain available. User-defined providers that depend on your normal configuration are not imported: use the API adapter for custom endpoints.

This is not an OS sandbox. System/managed configuration and the runtime's date/environment context may still apply. OpenCode may keep sessions in its normal data store; their IDs are included in report metadata. Use sanitized cases even when reports stay local.

References: [V2 commands](https://dev.opencode.ai/v2/docs/cli/commands/), [configuration](https://dev.opencode.ai/v2/docs/config/), [policies](https://dev.opencode.ai/v2/docs/policies/).

## Codex

Requires an installed, authenticated Codex CLI. Live-tested with **0.166.0**; older versions may lack the required flags.

```sh
codex login status
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-codex --model YOUR_MODEL_ID" \
  --out reports/codex.json
```

The adapter uses ephemeral sessions, fresh temporary directories, read-only sandboxing, and an explicit model with `high` reasoning by default. Change it with the adapter's `--reasoning` flag.

It replaces the built-in prompt, ignores user configuration/rules, disables project instructions, local skill discovery, integrations, hooks, and optional tools, and rejects unexpected tool activity. System-managed policies still apply. `skip_host_skill_discovery` is an experimental Codex flag: revalidate isolation when upgrading.

References: [noninteractive Codex](https://developers.openai.com/codex/noninteractive/), [configuration](https://developers.openai.com/codex/config-reference/).

## OpenAI-compatible APIs

Uses **`POST /chat/completions`**, not the Responses API. No provider SDK is required.

Set `OPENAI_API_KEY` using your normal secret-management workflow, then run:

```sh
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-openai --model YOUR_MODEL_ID" \
  --out reports/api.json
```

The default base URL is `https://api.openai.com/v1`. Set `OPENAI_BASE_URL`, or pass `--base-url`, to use another compatible service. Use `--api-key-env PROVIDER_API_KEY` to select a different environment variable; pass its **name**, never its value.

For a local server, such as an OpenAI-compatible model server listening on port 8000:

```sh
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-openai --base-url http://127.0.0.1:8000/v1 --api-key-env LOCAL_MODEL_KEY --model YOUR_LOCAL_MODEL" \
  --out reports/local.json
```

Loopback HTTP endpoints can run without a key; remote endpoints require HTTPS and a key. The base URL must not contain credentials, query parameters, or a fragment. Redirects are refused so authorization is not forwarded to another destination.

The default `--response-format json_object` asks for JSON mode. Use `json_schema` for endpoints supporting strict structured output, or `text` for endpoints without either feature. Even in text mode, the response must contain a JSON object without Markdown fences. Unsupported formats fail visibly; there is no silent fallback. Optional `--temperature` is omitted by default because some models reject it.

Truncation, refusal, tool calls, invalid JSON, and HTTP errors are failures—not ties. Reports include the requested/resolved model, settings, response fingerprint when supplied, and usage. Transport tests use a local HTTP server, including real runner-to-adapter calls; **hosted API compatibility has not been live-verified**.

Reference: [Chat Completions request/response contract](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create).

## Claude Code

For people who already have Claude Code installed and authenticated:

```sh
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-claude --model YOUR_CLAUDE_MODEL" \
  --out reports/claude.json
```

Requires a current CLI supporting `--safe-mode`, `--restricted`, and structured output. It runs print mode in a fresh directory, replaces the system prompt, disables built-in/MCP tools and hooks, ignores user/project settings, and disables session persistence. It accepts only a successful structured result; managed policy still applies.

**Status: implemented and fixture-tested, not live-verified.** Claude Code was neither installed nor run to test this adapter. Validate a small synthetic suite on your installation before using it as a gate; unsupported CLI flags fail rather than falling back to less restrictive execution.

Reference: [Claude Code CLI flags](https://code.claude.com/docs/en/cli-reference).

## Separate generator and judge

Use an independent judge model when practical:

```sh
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-opencode --model YOUR_PROVIDER/YOUR_MODEL" \
  --judge-adapter "volna-skillcheck-openai --model YOUR_JUDGE_MODEL" \
  --repeats 3 --out reports/independent-judge.json
```

This changes the judge, not the old/new generation settings. Swapped judgments and repeated trials can expose inconsistency; they cannot eliminate judge bias.

## Timeouts and diagnosis

Bundled adapters default to 90 seconds; the runner allows 120 seconds per invocation. Increase both for slower models, leaving room for CLI startup:

```sh
volna-skillcheck --old examples/old.md --new examples/new.md \
  --cases examples/cases.json \
  --adapter "volna-skillcheck-opencode --model YOUR_PROVIDER/YOUR_MODEL --timeout 180" \
  --timeout 210 --out reports/slower-model.json
```

Failed calls are retained in the report with a stage and diagnostic code. The runner intentionally does not copy raw stderr, which may contain secrets. To troubleshoot, send a **synthetic** request from the [protocol guide](protocol.md) directly to the adapter and inspect its safe diagnostic code. API 401/403 means check credentials/access; 429 means check quota/rate limits. There are no automatic paid retries.
