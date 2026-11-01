"""Codex CLI adapter for volna-skillcheck's JSON stdin/stdout protocol (Linux/macOS)."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
import tempfile

from volna_skillcheck import AdapterError, MAX_BYTES, __version__, decode_json, digest, nonempty, process, read_input

from volna_skillcheck_adapter import prepare, validate_result


def evaluate(request, model, reasoning="high", timeout=90, executable="codex"):
    instructions, prompt, schema = prepare(request)
    isolate = os.environ.get("_VOLNA_SKILLCHECK_MANAGED") != "1"
    cli_version = process([executable, "--version"], "", 10, isolate=isolate).strip()
    with tempfile.TemporaryDirectory(prefix="volna-skillcheck-codex-") as directory:
        root = Path(directory)
        (root / "instructions.txt").write_text(instructions, encoding="utf-8")
        (root / "schema.json").write_text(json.dumps(schema), encoding="utf-8")
        command = [executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral",
                   "--skip-git-repo-check", "--sandbox", "read-only", "--model", model,
                   "--json", "--color", "never", "--output-schema", str(root / "schema.json"),
                   "--output-last-message", str(root / "answer.json"),
                   "-c", 'approval_policy="never"', "-c", "project_doc_max_bytes=0",
                   "-c", "suppress_unstable_features_warning=true",
                   "-c", 'web_search="disabled"', "-c", "model_reasoning_effort=" + json.dumps(reasoning),
                   "-c", "model_instructions_file=" + json.dumps(str(root / "instructions.txt")),
                   "--enable", "skip_host_skill_discovery"]
        for feature in ("shell_tool", "apps", "plugins", "hooks", "multi_agent", "skill_search",
                        "browser_use", "computer_use", "image_generation", "view_image"):
            command.extend(["--disable", feature])
        events = process(command + ["-"], prompt, timeout, cwd=directory, isolate=isolate)
        usage = None
        completed = False
        for line in events.splitlines():
            event = decode_json(line)
            if event.get("type") in ("error", "turn.failed"):
                raise AdapterError("codex_turn_failed")
            if event.get("type", "").startswith("item."):
                if event.get("item", {}).get("type") not in ("agent_message", "reasoning"):
                    raise AdapterError("codex_unexpected_tool_activity")
            if event.get("type") == "turn.completed":
                completed = True
                usage = event.get("usage")
        if not completed:
            raise AdapterError("codex_incomplete_turn")
        result = validate_result(decode_json(read_input(root / "answer.json")), request["operation"])
        result["metadata"] = {"adapter": "volna-skillcheck-codex", "adapter_version": __version__,
            "cli_version": cli_version, "model": model, "reasoning_effort": reasoning,
            "instructions_sha256": digest(instructions), "prompt_sha256": digest(prompt), "usage": usage}
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True, help="Explicit Codex model ID; pin a snapshot when available")
    parser.add_argument("--reasoning", choices=("low", "medium", "high", "xhigh"), default="high")
    parser.add_argument("--timeout", type=float, default=90, help="Codex call timeout, below runner --timeout")
    args = parser.parse_args(argv)
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise ValueError("Invalid timeout")
        raw = sys.stdin.buffer.read(MAX_BYTES + 1)
        if len(raw) > MAX_BYTES:
            raise ValueError("Request too large")
        result = evaluate(decode_json(raw), args.model, args.reasoning, args.timeout)
    except (AdapterError, OSError, ValueError) as error:
        print("volna-skillcheck-codex: " + (str(error) if isinstance(error, AdapterError) else type(error).__name__), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
