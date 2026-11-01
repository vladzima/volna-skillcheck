# Security

volna-skillcheck runs trusted adapter executables with the invoking user's permissions and inherited environment. It is not a sandbox for untrusted commands. Process groups, timeouts, and output limits provide cleanup for ordinary adapters, not containment against a malicious executable that escapes its process group.

The Codex adapter requests a read-only sandbox and disables local configuration, skill discovery, hooks, integrations, and optional tools. System-managed policies still apply. Test isolation again when upgrading Codex, especially its experimental skill-discovery flag. Treat cases and model answers as untrusted data; the blind judge can still be susceptible to prompt injection.

The OpenCode V2 adapter starts a private server with temporary user configuration and denies tools, skills, plugins, and MCP. System-managed settings may still apply. Its credentials and session storage remain in OpenCode's normal data location; sanitized evaluation sessions may remain there. The Claude Code adapter requests safe/restricted mode, disables tools and hooks, and avoids session persistence; it has not been live-verified. Neither adapter is an OS sandbox.

The API adapter requires HTTPS for remote hosts, allows HTTP only on loopback, and refuses redirects rather than forwarding authorization. Keys are read from environment variables. An explicitly selected endpoint receives the selected key: use a separate key variable for local or third-party providers. Raw HTTP error bodies are not copied into reports.

Reports contain exact instructions, contexts, model answers, and adapter-supplied metadata. They are sensitive even when file permissions are restrictive. Review and sanitize them before sharing. Provider retention and logging policies are outside volna-skillcheck's control. The project does not send telemetry.

Only the latest released version will receive fixes. Report vulnerabilities through [GitHub's private reporting form](https://github.com/vladzima/volna-skillcheck/security/advisories/new). Do not put credentials or exploit payloads containing private data in public issues.
