"""Claude Code adapter. Requires a CLI with --safe-mode and --restricted support."""
import json
import os
from pathlib import Path
import sys
import tempfile

from volna_skillcheck import AdapterError, __version__, decode_json, digest, process
from volna_skillcheck_adapter import adapter_main, adapter_parser, prepare, validate_result


def evaluate(request, model, timeout=90, executable="claude"):
    instructions, prompt, schema = prepare(request)
    isolate = os.environ.get("_VOLNA_SKILLCHECK_MANAGED") != "1"
    with tempfile.TemporaryDirectory(prefix="volna-skillcheck-claude-") as directory:
        root = Path(directory)
        system = root / "instructions.txt"
        system.write_text(instructions, encoding="utf-8")
        version = process([executable, "--version"], "", 10, cwd=directory, isolate=isolate).strip()
        command = [executable, "-p", "--model", model, "--output-format", "json",
                   "--json-schema", json.dumps(schema), "--system-prompt-file", str(system),
                   "--safe-mode", "--restricted", "--tools", "", "--disallowedTools", "*",
                   "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                   "--setting-sources", "", "--settings", '{"disableAllHooks":true}',
                   "--no-session-persistence"]
        raw = process(command, prompt, timeout, cwd=directory, isolate=isolate)
        envelope = decode_json(raw)
        if (not isinstance(envelope, dict) or envelope.get("type") != "result"
                or envelope.get("subtype") != "success" or envelope.get("is_error") is not False):
            raise AdapterError("claude_incomplete_turn")
        result = validate_result(envelope.get("structured_output"), request["operation"])
        result["metadata"] = {"adapter": "volna-skillcheck-claude", "adapter_version": __version__,
            "cli_version": version, "model": model, "instructions_sha256": digest(instructions),
            "prompt_sha256": digest(prompt), "usage": envelope.get("usage"),
            "model_usage": envelope.get("modelUsage"), "cost_usd": envelope.get("total_cost_usd")}
        return result


def main(argv=None):
    return adapter_main(adapter_parser(__doc__), evaluate, argv)


if __name__ == "__main__":
    sys.exit(main())
