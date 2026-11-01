# Use it with your agent

For the shortest path, [install the volna-skillcheck skill](skill.md) and ask your agent to check the change. It prepares the inputs and runs a bounded comparison. The workflows below show the manual steps and optional integrations.

Start with a real instruction change and a few **sanitized decision points**. You do not need to export an entire chat, wire up an agent SDK, or replace your existing assistant.

The adapter chooses which runtime/model answers and judges. The instruction file chooses what you are testing. You can test `CLAUDE.md` with the API adapter, or a Hermes skill through OpenCode—just don't interpret that as a test of the original runtime's skill discovery or tool execution.

## 1. Test an AGENTS.md change

In your own project, after editing `AGENTS.md`:

```sh
mkdir -p .skillcheck
git show HEAD:AGENTS.md > .skillcheck/before.md
cp AGENTS.md .skillcheck/after.md
```

`HEAD` must contain the baseline version you want to compare. If the file is new, supply a meaningful baseline instruction instead. Keep `.skillcheck/` ignored locally; don't accidentally commit private evaluation data.

Create `.skillcheck/cases.json` using this format:

```json
[
  {
    "id": "started-but-unverified",
    "input": "Is the import finished?",
    "context": "The import returned a process ID. No completion event or destination count is available.",
    "criteria": "Say it started, distinguish that from completion, and identify the missing outcome check."
  },
  {
    "id": "verified-success",
    "input": "Is the import finished?",
    "context": "The import exited zero. The destination contains all 42 requested records, with matching IDs.",
    "criteria": "Confirm completion from the evidence. Do not invent missing checks or unnecessary hesitation."
  }
]
```

Then run with a model available in OpenCode:

```sh
volna-skillcheck \
  --old .skillcheck/before.md --new .skillcheck/after.md \
  --cases .skillcheck/cases.json \
  --adapter "volna-skillcheck-opencode --model openai/gpt-6-astra#high" \
  --out .skillcheck/first-report.json
```

Open the report and inspect the answers. These two cases can expose a regression; they cannot establish a five-case candidate improvement. Add distinct tasks representative of your work, including successful baselines, before making a promotion decision. Keep some examples held out while developing the rule.

For `CLAUDE.md` or another instruction file, change the snapshot paths. The rest of the process is the same.

## 2. Test a skill revision

Save the previous and edited `SKILL.md` as the before/after files, then write cases that the skill is intended to handle. Recorded tool results go in `context`; the expected behavior goes in `criteria`.

If the skill depends on a referenced file, include the relevant, sanitized contents in **both** revision inputs or in the shared context. Adapters cannot fetch references or execute tools. Frontmatter is treated as text: this tests the instruction's effect on answers, not whether a runtime discovers or invokes the skill correctly.

This also works with skills used in Hermes, Codex, OpenCode, or Claude Code. Only the bundled adapters listed in the README are implemented; there is no native Hermes adapter.

A useful request to your existing agent:

> Prepare a before/after instruction comparison with volna-skillcheck. Use sanitized cases covering the failure that motivated this edit and tasks where the old instruction already worked. Keep the evaluation data local. Run the chosen adapter, wait for completion, and show the saved evidence for regressions or uncertainty. Do not apply the new instruction automatically.

## 3. Add an OpenCode /skillcheck command

The repository includes a [command template](../examples/integrations/opencode-skillcheck.md). Copy it to `.opencode/commands/skillcheck.md` in the project where you want to use it. For a command in every project, use `~/.config/opencode/commands/skillcheck.md` instead.

Inside OpenCode, run:

```text
/skillcheck Compare the verification-rule edit using openai/gpt-6-astra#high
```

The command guides the agent through the three input files, running the evaluation, and reviewing the report. It does not automatically execute a shell block, modify instructions, or publish anything. The agent still needs permission to run the CLI, and the CLI must be on its `PATH`—activate the virtual environment before launching OpenCode, or install the tool into a suitable environment.

OpenCode reloads command files automatically. This template uses the [documented V2 command format](https://dev.opencode.ai/v2/docs/commands/); it is an optional user-installed prompt, not a plugin or background service.

## 4. Run a manual check in GitHub Actions

Copy [evaluate-instructions.yml](../examples/integrations/evaluate-instructions.yml) into your project's `.github/workflows/` directory. It expects:

- Reviewed, sanitized `eval/before.md`, `eval/after.md`, and `eval/cases.json` in that repository.
- An `OPENAI_API_KEY` repository secret.
- An explicit model ID when you choose **Run workflow** in GitHub Actions.

The example is manually triggered so an untrusted pull request cannot start a paid evaluation with your key. It installs a pinned release, passes the model through an environment variable without shell interpolation, and treats every nonzero evaluation exit as a failed gate. Reports are not uploaded automatically because they contain complete task data.

This is a template for your own project; it is not enabled in volna-skillcheck's CI. The project's own CI uses offline fixtures and spends no model quota.
