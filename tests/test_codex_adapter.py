import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import volna_skillcheck_codex as c
from volna_skillcheck import AdapterError

REQUEST = {"operation": "generate", "instruction": "Be careful", "input": "Done?", "context": "Started"}


class CodexTests(unittest.TestCase):
    def test_prompt_keeps_generation_and_judge_separate(self):
        instructions, prompt, schema = c.prepare(REQUEST)
        self.assertIn("Be careful", instructions)
        self.assertEqual(json.loads(prompt), {"input": "Done?", "context": "Started"})
        self.assertEqual(schema["required"], ["text"])
        instructions, prompt, schema = c.prepare({"operation": "judge", "input": "Done?", "context": "Started",
                                                 "criteria": "Evidence", "a": "Yes", "b": "No"})
        self.assertNotIn("Be careful", instructions + prompt)
        self.assertEqual(schema["properties"]["winner"]["enum"], ["a", "b", "tie", "abstain"])
        for bad in ([], {}, {"operation": "shell"}, dict(REQUEST, context=[])):
            with self.assertRaises(ValueError):
                c.prepare(bad)

    def test_fake_codex_executable_protocol_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "codex"
            executable.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
if '--version' in sys.argv:
    print('codex-cli fixture')
    sys.exit(0)
assert '--ignore-user-config' in sys.argv
assert '--ignore-rules' in sys.argv
assert '--ephemeral' in sys.argv
assert sys.argv[sys.argv.index('--sandbox') + 1] == 'read-only'
assert 'project_doc_max_bytes=0' in sys.argv
assert 'skip_host_skill_discovery' in sys.argv
request = json.load(sys.stdin)
assert request['context'] == 'Started'
pathlib.Path(sys.argv[sys.argv.index('--output-last-message') + 1]).write_text(json.dumps({'text': 'Not verified'}))
print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'ignored transport copy'}}))
print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 10, 'output_tokens': 2}}))
''')
            executable.chmod(0o700)
            result = c.evaluate(REQUEST, "test-model", executable=str(executable))
        self.assertEqual(result["text"], "Not verified")
        self.assertEqual(result["metadata"]["model"], "test-model")
        self.assertEqual(result["metadata"]["usage"]["output_tokens"], 2)
        self.assertEqual(result["metadata"]["cli_version"], "codex-cli fixture")

    def test_incomplete_or_tool_turn_is_rejected(self):
        for event, error in (({"type": "turn.failed"}, "codex_turn_failed"),
                             ({"type": "thread.started"}, "codex_incomplete_turn"),
                             ({"type": "item.started", "item": {"type": "command_execution"}}, "codex_unexpected_tool_activity")):
            with patch.object(c, "process", side_effect=["codex-cli fixture", json.dumps(event)]):
                with self.assertRaisesRegex(AdapterError, error):
                    c.evaluate(REQUEST, "test-model")

    def test_nested_adapter_stays_in_runner_process_group(self):
        with patch.dict(os.environ, {"_VOLNA_SKILLCHECK_MANAGED": "1"}):
            with patch.object(c, "process", side_effect=["codex-cli fixture", ""]) as process:
                with self.assertRaises(AdapterError):
                    c.evaluate(REQUEST, "test-model")
        self.assertTrue(all(call.kwargs["isolate"] is False for call in process.call_args_list))


if __name__ == "__main__":
    unittest.main()
