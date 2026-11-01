# Contributing

Keep the core small and provider-independent. Use Python's standard library unless a dependency substantially simplifies a necessary feature. Preserve error handling, evidence, and conservative verdicts when changing the evaluation flow.

Run `python3 -m unittest discover -s tests -v`. Tests must be offline, deterministic, and not depend on local credentials. Include a regression test for behavior changes. CLI changes must be tested through a subprocess, including exit codes. Protocol or report changes require documentation and, for incompatible report changes, a schema version increment.

New cases should be synthetic or explicitly cleared for publication. Include a meaningful criterion and positive controls where applicable. Never add real conversations, customer data, access tokens, live identifiers, or private tool transcripts. Literal checks should test actual requirements rather than a preferred writing style.

For provider adapters, test protocol handling with a fake provider and run a small live smoke test before claiming compatibility. Record the tested provider/CLI version and limitations. Do not commit live reports. Contributions are provided under the project's MIT license.
