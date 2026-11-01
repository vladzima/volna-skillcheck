import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import volna_skillcheck as core
import volna_skillcheck_claude as claude
import volna_skillcheck_openai as api
import volna_skillcheck_opencode as opencode
from volna_skillcheck_adapter import validate_result

REQUEST = {"operation": "generate", "instruction": "baseline", "input": "Done?", "context": "Started"}
ROOT = Path(__file__).resolve().parents[1]


def completion(text, **updates):
    result = {"model": "resolved-model", "choices": [{"finish_reason": "stop", "message": {
        "content": json.dumps(text)}}], "usage": {"completion_tokens": 10}}
    result.update(updates)
    return result


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append((self.path, dict(self.headers), body))
        if self.server.response is None:
            system, user = body["messages"]
            data = json.loads(user["content"])
            if "Instruction revision:" in system["content"]:
                answer = {"text": "improved" if "improved" in system["content"] else "baseline"}
            else:
                answer = {"winner": "a" if data["a"] == "improved" else "b", "reason": "Evidence"}
            response = completion(answer)
        else:
            response = self.server.response
        raw = response if isinstance(response, bytes) else json.dumps(response).encode()
        self.send_response(self.server.status)
        if self.server.status == 302:
            self.send_header("Location", self.server.base_url + "/stolen")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args):
        pass


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.base_url = f"http://127.0.0.1:{self.server.server_port}/v1"
        self.server.calls = []
        self.server.response = None
        self.server.status = 200
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.environment = patch.dict(os.environ, {"SKILLCHECK_TEST_KEY": "private-fixture-key"})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def evaluate(self, request=REQUEST, **options):
        return api.evaluate(request, "test-model", base_url=self.server.base_url,
                            api_key_env="SKILLCHECK_TEST_KEY", **options)

    def test_real_http_protocol_and_metadata(self):
        result = self.evaluate()
        path, headers, body = self.server.calls[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer private-fixture-key")
        self.assertFalse(body["stream"])
        self.assertNotIn("tools", body)
        self.assertNotIn("temperature", body)
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertEqual(json.loads(body["messages"][1]["content"]), {"input": "Done?", "context": "Started"})
        self.assertEqual(result["text"], "baseline")
        self.assertEqual(result["metadata"]["resolved_model"], "resolved-model")
        self.assertNotIn("private-fixture-key", json.dumps(result))

    def test_formats_and_validation(self):
        self.evaluate(response_format="json_schema", temperature=0)
        body = self.server.calls[-1][2]
        self.assertTrue(body["response_format"]["json_schema"]["strict"])
        self.assertEqual(body["temperature"], 0)
        self.evaluate(response_format="text")
        self.assertNotIn("response_format", self.server.calls[-1][2])
        for value in (float("nan"), -1, 3):
            with self.assertRaises(ValueError):
                self.evaluate(temperature=value)

    def test_errors_refusals_truncation_and_malformed_output(self):
        for response, expected in [
            (completion({"text": "ok"}, choices=[{"finish_reason": "length", "message": {"content": "x"}}]), "api_incomplete_response"),
            (completion({"text": "ok"}, choices=[{"finish_reason": "stop", "message": {"tool_calls": [1]}}]), "api_unexpected_response"),
            (completion({"text": "ok"}, choices=[{"finish_reason": "stop", "message": {"refusal": "no"}}]), "api_unexpected_response"),
            ({"choices": []}, "api_invalid_response"), (b"not-json", "api_invalid_response"),
            (completion({"text": ""}), "model_invalid_response")]:
            self.server.response = response
            with self.assertRaisesRegex(core.AdapterError, expected):
                self.evaluate()
        self.server.response = b"x" * 65
        with patch.object(api, "MAX_BYTES", 64):
            with self.assertRaisesRegex(core.AdapterError, "api_response_too_large"):
                self.evaluate()
        self.server.status = 401
        self.server.response = b"private-fixture-key"
        with self.assertRaisesRegex(core.AdapterError, "^api_http_401$"):
            self.evaluate()

    def test_redirect_never_receives_credentials(self):
        self.server.status = 302
        with self.assertRaisesRegex(core.AdapterError, "api_redirect_refused"):
            self.evaluate()
        self.assertEqual(len(self.server.calls), 1)

    def test_installed_protocol_via_runner_and_adapter_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "old.md").write_text("baseline")
            (root / "new.md").write_text("improved")
            (root / "cases.json").write_text(json.dumps([{"id": "one", "input": "Done?", "criteria": "Evidence"}]))
            command = [sys.executable, str(ROOT / "volna_skillcheck.py"), "--old", str(root / "old.md"),
                       "--new", str(root / "new.md"), "--cases", str(root / "cases.json"), "--min-wins", "1",
                       "--adapter", shlex.join([sys.executable, str(ROOT / "volna_skillcheck_openai.py"),
                        "--model", "test-model", "--base-url", self.server.base_url, "--api-key-env", "SKILLCHECK_TEST_KEY"]),
                       "--out", str(root / "report.json")]
            run = subprocess.run(command, cwd=directory, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
            report = json.loads((root / "report.json").read_text())
            self.assertEqual(len(report["cases"][0]["trials"][0]["judgments"]), 2)
            self.assertNotIn("private-fixture-key", json.dumps(report))
            self.assertEqual(len(self.server.calls), 4)


class AdapterTests(unittest.TestCase):
    def test_endpoint_security_and_missing_auth(self):
        for url in ("http://example.com/v1", "https://key@example.com/v1", "https://host/v1?key=x",
                    "https://host/v1#key", "file:///tmp/api"):
            with self.assertRaises(ValueError):
                api.endpoint(url)
        self.assertEqual(api.endpoint("http://[::1]:8080/v1")[1], True)
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(core.AdapterError, "api_key_missing"):
                api.evaluate(REQUEST, "test")

    def test_shared_validation_discards_model_metadata(self):
        self.assertEqual(validate_result({"text": "ok", "metadata": {"secret": "bad"}}, "generate"), {"text": "ok"})
        for result in ([], None, {"winner": "old", "reason": "x"}):
            with self.assertRaises(core.AdapterError):
                validate_result(result, "judge")

    def test_claude_flags_prompt_and_structured_result(self):
        def fake(command, payload, timeout, **kwargs):
            if "--version" in command:
                return "Claude Code fixture"
            self.assertTrue({"--safe-mode", "--restricted", "--no-session-persistence", "--strict-mcp-config"} <= set(command))
            self.assertEqual(command[command.index("--tools") + 1], "")
            self.assertEqual(command[command.index("--disallowedTools") + 1], "*")
            self.assertEqual(command[command.index("--setting-sources") + 1], "")
            self.assertIn("baseline", Path(command[command.index("--system-prompt-file") + 1]).read_text())
            self.assertEqual(json.loads(payload)["input"], "Done?")
            return json.dumps({"type": "result", "subtype": "success", "is_error": False,
                               "structured_output": {"text": "Not verified"}, "usage": {"input_tokens": 10}})
        with patch.object(claude, "process", side_effect=fake):
            result = claude.evaluate(REQUEST, "test-model")
        self.assertEqual(result["text"], "Not verified")
        for envelope in ({}, {"type": "result", "subtype": "error_max_turns", "is_error": True}):
            with patch.object(claude, "process", side_effect=["version", json.dumps(envelope)]):
                with self.assertRaisesRegex(core.AdapterError, "claude_incomplete_turn"):
                    claude.evaluate(REQUEST, "test-model")

    def test_opencode_isolated_config_and_event_protocol(self):
        def fake(command, payload, timeout, **kwargs):
            env = kwargs["env"]
            self.assertNotIn("OPENCODE_CONFIG_CONTENT", env)
            config = json.loads((Path(env["XDG_CONFIG_HOME"]) / "opencode/opencode.json").read_text())
            self.assertEqual(config["permissions"], [{"action": "*", "resource": "*", "effect": "deny"}])
            self.assertEqual({p["action"] for p in config["policies"]}, {"tool.use", "skill.use", "mcp.use", "plugin.use"})
            self.assertIn("baseline", config["agents"]["skillcheck"]["system"])
            self.assertEqual(env["OPENCODE_DISABLE_PROJECT_CONFIG"], "1")
            if "--version" in command:
                return "opencode v2.2.5"
            self.assertIn("--standalone", command)
            self.assertNotIn("--auto", command)
            self.assertEqual(json.loads(payload)["context"], "Started")
            return '\n'.join(json.dumps(e) for e in [
                {"type": "step_start", "sessionID": "test-session"},
                {"type": "text", "part": {"text": '{"text":"Not verified"}'}},
                {"type": "step_finish", "part": {"reason": "stop", "tokens": {"output": 3}}}])
        with patch.dict(os.environ, {"OPENCODE_CONFIG_CONTENT": '{"unsafe":true}'}):
            with patch.object(opencode, "process", side_effect=fake):
                result = opencode.evaluate(REQUEST, "openai/test-model")
        self.assertEqual(result["text"], "Not verified")
        self.assertEqual(result["metadata"]["session_id"], "test-session")

    def test_opencode_rejects_unsupported_versions_tools_and_incomplete_turns(self):
        for version in ("opencode 1.2.3", "opencode v2.2.2", "opencode v3.0.0", "unknown"):
            with patch.object(opencode, "process", return_value=version):
                with self.assertRaisesRegex(core.AdapterError, "opencode_requires"):
                    opencode.evaluate(REQUEST, "model")
        for event, error in (({"type": "tool_use"}, "opencode_unexpected_event"),
                             ({"type": "error"}, "opencode_turn_failed"),
                             ({"type": "step_finish", "part": {"reason": "length"}}, "opencode_incomplete_turn")):
            with patch.object(opencode, "process", side_effect=["opencode v2.2.5", json.dumps(event)]):
                with self.assertRaisesRegex(core.AdapterError, error):
                    opencode.evaluate(REQUEST, "model")


if __name__ == "__main__":
    unittest.main()
