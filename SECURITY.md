# Security

volna-skillcheck runs trusted adapter executables with the invoking user's permissions and inherited environment. It is not a sandbox for untrusted commands. Process groups, timeouts, and output limits provide cleanup for ordinary adapters, not containment against a malicious executable that escapes its process group.

The Codex adapter requests a read-only sandbox and disables local configuration, skill discovery, hooks, integrations, and optional tools. System-managed policies still apply. Test isolation again when upgrading Codex, especially its experimental skill-discovery flag. Treat cases and model answers as untrusted data; the blind judge can still be susceptible to prompt injection.

Reports contain exact instructions, contexts, model answers, and adapter-supplied metadata. They are sensitive even when file permissions are restrictive. Review and sanitize them before sharing. Provider retention and logging policies are outside volna-skillcheck's control. The project does not send telemetry.

Only the latest released version will receive fixes. Report vulnerabilities through [GitHub's private reporting form](https://github.com/vladzima/volna-skillcheck/security/advisories/new). Do not put credentials or exploit payloads containing private data in public issues.
