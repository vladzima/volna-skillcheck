"""OpenCode V2 adapter (2.2.3+), using a private server and a tool-denied agent."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from volna_skillcheck import AdapterError, __version__, decode_json, digest, nonempty, process
from volna_skillcheck_adapter import adapter_main, adapter_parser, prepare, validate_result


def evaluate(request, model, timeout=90, executable="opencode"):
    instructions, prompt, schema = prepare(request)
    isolate = os.environ.get("_VOLNA_SKILLCHECK_MANAGED") != "1"
    with tempfile.TemporaryDirectory(prefix="volna-skillcheck-opencode-") as directory:
        root = Path(directory)
        config_dir = root / "config" / "opencode"
        config_dir.mkdir(parents=True)
        config = {"$schema": "https://opencode.ai/config.json", "share": "disabled", "update": "disable",
            "snapshots": False, "warming": False, "instructions": [], "skills": [],
            "permissions": [{"action": "*", "resource": "*", "effect": "deny"}],
            "policies": [{"action": action, "resource": "*", "effect": "deny"}
                         for action in ("tool.use", "skill.use", "mcp.use", "plugin.use")],
            "agents": {"skillcheck": {"mode": "primary", "system": instructions,
                "description": "Evaluate one recorded task without tools", "steps": 1,
                "permissions": [{"action": "*", "resource": "*", "effect": "deny"}]}}}
        (config_dir / "opencode.json").write_text(json.dumps(config), encoding="utf-8")
        # Preserve provider credentials, but not inherited OpenCode config/server overrides.
        env = {k: v for k, v in os.environ.items() if not k.startswith("OPENCODE_")}
        env.update(XDG_CONFIG_HOME=str(root / "config"), OPENCODE_DISABLE_PROJECT_CONFIG="1")
        version = process([executable, "--version"], "", 10, cwd=directory, isolate=isolate, env=env).strip()
        match = re.search(r"\bv?(\d+)\.(\d+)\.(\d+)\b", version)
        if not match or tuple(map(int, match.groups())) < (2, 2, 3) or int(match[1]) != 2:
            raise AdapterError("opencode_requires_v2_2_3_or_newer_v2")
        events = process([executable, "run", "--standalone", "--format", "json", "--model", model,
                          "--agent", "skillcheck"], prompt, timeout, cwd=directory, isolate=isolate, env=env)
        texts, usage, session_id, completed = [], None, None, False
        for line in events.splitlines():
            event = decode_json(line)
            if not isinstance(event, dict) or not isinstance(event.get("part", {}), dict):
                raise AdapterError("opencode_invalid_event")
            kind = event.get("type")
            part = event.get("part", {})
            session_id = event.get("sessionID", session_id)
            if kind == "error":
                raise AdapterError("opencode_turn_failed")
            if kind == "text":
                if not nonempty(part.get("text")):
                    raise AdapterError("opencode_invalid_event")
                texts.append(part["text"])
            elif kind == "step_finish":
                completed = part.get("reason") == "stop"
                usage = part.get("tokens")
            elif kind not in ("step_start", "reasoning"):
                raise AdapterError("opencode_unexpected_event")
        if not completed:
            raise AdapterError("opencode_incomplete_turn")
        result = validate_result(decode_json("".join(texts)), request["operation"])
        result["metadata"] = {"adapter": "volna-skillcheck-opencode", "adapter_version": __version__,
            "cli_version": version, "model": model, "session_id": session_id,
            "instructions_sha256": digest(instructions), "prompt_sha256": digest(prompt), "usage": usage}
        return result


def main(argv=None):
    return adapter_main(adapter_parser(__doc__), evaluate, argv)


if __name__ == "__main__":
    sys.exit(main())
