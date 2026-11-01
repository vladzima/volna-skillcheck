# What a result establishes

volna-skillcheck evaluates an assistant's **answer at a recorded decision point**. Context is supplied as text; the runner does not execute recorded tools, resume the original conversation, test scheduling/recovery, or prove that a promised action occurred. Those properties need an agent harness with observable actions and outcome assertions. A fluent answer about verification can still be wrong in a live workflow.

For each case and repeat:

1. Randomize which revision generates first. Give both identical task/context.
2. Apply any literal answer checks independently to each revision.
3. If answer strings are identical, record a tie without spending judge calls.
4. Otherwise, judge a seeded anonymous presentation and the swapped presentation, independently. Retain both reasons.
5. Require mapped judgments to agree. Disagreement becomes `unstable`; any abstention becomes `abstain`. A baseline pass with a candidate check failure is a regression regardless of judge preference.

Across repeats, any established regression makes the case a regression. Otherwise, all repeats must agree for a win or tie. Abstention or inconsistent results prevents a positive overall verdict. An error marks the case incomplete without deleting its successful calls. Across cases, any error makes the run incomplete; any regression blocks promotion. Failed candidate checks block promotion even when the baseline also fails. Any remaining uncertainty blocks promotion. At least five distinct candidate wins are required by default; ties do not count as wins.

This policy is deliberately conservative, but **five wins is a heuristic, not a confidence interval**. Correlated cases, prompt leakage, judge self-preference, verbosity bias, repeated tuning, and nondeterministic generation all limit inference. Swapping presentation helps reveal position bias; it does not eliminate judge bias or prompt injection. A malicious answer can influence both judgments. Use deterministic checks where appropriate and inspect the saved evidence before accepting a change.

Good evaluation practice:

- Keep a development suite and a held-out suite; avoid repeatedly tuning against the holdout.
- Include baseline successes so a rule that adds needless hesitation can regress.
- Prefer multiple task families over many paraphrases of one failure.
- Use an independent judge model and human review for consequential changes.
- Record the suite, model snapshot, adapter version, and settings alongside the report.
- Test live agent behavior separately before shipping changes that affect external actions.

The included mock fixture always follows a hand-written preference. Its wins demonstrate report mechanics. They are not evidence that the example instruction improves a real model. A live two-case smoke test establishes adapter compatibility, not the quality or reliability of any instruction set.
