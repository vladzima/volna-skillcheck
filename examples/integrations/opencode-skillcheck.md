---
description: Compare instruction revisions on recorded tasks
---
Evaluate the instruction change using volna-skillcheck. The user's optional context is:
$ARGUMENTS

Use .skillcheck/before.md, .skillcheck/after.md, and .skillcheck/cases.json in this project.
If any file is missing, help the user create it from sanitized examples before running.
Do not put real credentials or private conversations into a case. Include tasks where the
baseline already worked. Keep evaluation files out of version control unless the user
has reviewed them for publication.

Confirm that volna-skillcheck and volna-skillcheck-opencode are available. Use an explicit
provider/model already available in OpenCode; ask which model if the user has not selected
one. Explain that each case costs up to four model calls per repeat. Use a fresh report
path under .skillcheck/ for every run.

Run this command with the selected model and report path substituted and shell-quoted:
volna-skillcheck --old .skillcheck/before.md --new .skillcheck/after.md --cases .skillcheck/cases.json --adapter "volna-skillcheck-opencode --model PROVIDER/MODEL" --out .skillcheck/REPORT.json

Wait for the command to finish, then read the report. Report the verdict, any regressions,
failed checks, disagreements, and errors. Quote the relevant saved answer evidence. Treat
insufficient_data and inconclusive as uncertainty. Do not lower --min-wins to make a change
pass. Do not overwrite active instructions, commit, publish, or claim the agent's full
workflow was verified based on this evaluation.
