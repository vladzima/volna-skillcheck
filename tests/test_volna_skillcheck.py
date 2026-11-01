import copy
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import volna_skillcheck as s

CASES = [{"id": "one", "input": "Do it", "context": "Recorded tools", "criteria": "Verify"}]
ROOT = Path(__file__).resolve().parents[1]


def good_adapter(command, request, timeout):
    if request["operation"] == "generate":
        return {"text": request["instruction"], "metadata": {"model": "fixture"}}
    return {"winner": "tie" if request["a"] == request["b"] else "a" if request["a"] == "improved" else "b",
            "reason": "Fixture prefers improved"}


class EvaluationTests(unittest.TestCase):
    def evaluate(self, cases=None, **kwargs):
        return s.run("baseline", "improved", cases or CASES, "unused", **kwargs)

    def test_blind_mapping_and_swapped_context(self):
        for seed in range(10):
            with patch.object(s, "invoke", side_effect=good_adapter) as invoke:
                report = self.evaluate(seed=seed, min_wins=1)
            self.assertEqual(report["summary"]["verdict"], "candidate_improvement")
            requests = [c.args[1] for c in invoke.call_args_list]
            self.assertEqual(len(requests), 4)
            for r in requests:
                self.assertEqual(r["input"], "Do it")
                self.assertEqual(r["context"], "Recorded tools")
            first, second = requests[2:]
            self.assertEqual(set(first), {"operation", "input", "context", "criteria", "a", "b"})
            self.assertEqual(first["a"], second["b"])
            self.assertEqual(first["b"], second["a"])
            for r in requests[:2]:
                self.assertNotIn("criteria", r)
                self.assertNotIn("checks", r)

    def test_position_bias_and_abstention_are_not_wins(self):
        for winner, outcome in (("a", "unstable"), ("b", "unstable"), ("abstain", "abstain"), ("tie", "tie")):
            def adapter(command, request, timeout):
                return good_adapter(command, request, timeout) if request["operation"] == "generate" else {"winner": winner, "reason": "fixture"}
            with patch.object(s, "invoke", side_effect=adapter):
                report = self.evaluate(min_wins=1)
            self.assertEqual(report["summary"][outcome], 1)
            self.assertEqual(report["summary"]["verdict"], "inconclusive")

    def test_minimum_is_distinct_cases_not_repeated_votes(self):
        with patch.object(s, "invoke", side_effect=good_adapter):
            report = self.evaluate(repeats=6)
            many = self.evaluate(cases=[dict(CASES[0], id=str(i)) for i in range(5)])
        self.assertEqual(report["summary"]["new"], 1)
        self.assertEqual(report["summary"]["verdict"], "insufficient_data")
        self.assertEqual(many["summary"]["verdict"], "candidate_improvement")

    def test_identical_answers_skip_judge_and_remain_ties(self):
        with patch.object(s, "invoke", return_value={"text": "same"}) as invoke:
            report = self.evaluate()
        self.assertEqual(invoke.call_count, 2)
        self.assertEqual(report["summary"]["tie"], 1)
        self.assertEqual(report["cases"][0]["trials"][0]["judge_skipped"], "identical_answers")

    def test_regression_is_not_outvoted(self):
        def adapter(command, request, timeout):
            if request["operation"] == "generate":
                return {"text": request["instruction"]}
            preferred = "baseline" if request["input"] == "regress" else "improved"
            return {"winner": "a" if request["a"] == preferred else "b", "reason": "fixture"}
        cases = [dict(CASES[0], id=str(i), input="regress" if i == 0 else "win") for i in range(6)]
        with patch.object(s, "invoke", side_effect=adapter):
            report = self.evaluate(cases=cases)
        self.assertEqual(report["summary"]["old"], 1)
        self.assertEqual(report["summary"]["new"], 5)
        self.assertEqual(report["summary"]["verdict"], "regression")
        self.assertEqual(s.combine(["new", "old", "new"]), "old")
        self.assertEqual(s.combine(["new", "tie"]), "unstable")

    def test_failure_preserves_answers_and_continues(self):
        calls = 0
        def adapter(command, request, timeout):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise s.AdapterError("adapter_timeout")
            return good_adapter(command, request, timeout)
        with patch.object(s, "invoke", side_effect=adapter):
            report = self.evaluate(cases=CASES + [dict(CASES[0], id="two")])
        trial = report["cases"][0]["trials"][0]
        self.assertEqual(len(trial["answers"]), 2)
        self.assertEqual(len(trial["judgments"]), 1)
        self.assertEqual(trial["stage"], "judge_2")
        self.assertEqual(report["summary"]["errors"], 1)
        self.assertEqual(report["summary"]["new"], 1)
        self.assertEqual(report["summary"]["verdict"], "incomplete")

    def test_invalid_responses_become_errors(self):
        for invalid in (None, [], {}, {"text": 7}, {"text": " "}):
            with patch.object(s, "invoke", return_value=invalid):
                self.assertEqual(self.evaluate()["summary"]["errors"], 1)
        for invalid in (None, [], {"winner": "new", "reason": "bad"}, {"winner": "a", "reason": ""}):
            with patch.object(s, "invoke", side_effect=[{"text": "a"}, {"text": "b"}, invalid]):
                self.assertEqual(self.evaluate()["summary"]["errors"], 1)

    def test_validation_happens_before_any_call(self):
        invalids = [[], {}, CASES + CASES, [None], [dict(CASES[0], context={})],
                    [dict(CASES[0], criteria="")], [dict(CASES[0], check={})],
                    [dict(CASES[0], checks={"regex": ["x"]})],
                    [dict(CASES[0], checks={"contains": "x"})]]
        with patch.object(s, "invoke") as invoke:
            for cases in invalids:
                with self.assertRaises(ValueError):
                    s.run("a", "b", cases, "unused")
            for options in ({"timeout": float("nan")}, {"timeout": float("inf")}, {"repeats": 0}, {"min_wins": -1}):
                with self.assertRaises(ValueError):
                    self.evaluate(**options)
            invoke.assert_not_called()

    def test_checks_block_bad_candidate_even_when_judge_prefers_it(self):
        with patch.object(s, "invoke", side_effect=good_adapter):
            regression = self.evaluate(cases=[dict(CASES[0], checks={"contains": ["baseline"]})], min_wins=1)
            both_fail = self.evaluate(cases=[dict(CASES[0], checks={"contains": ["missing"]})], min_wins=1)
        self.assertEqual(regression["summary"]["verdict"], "regression")
        self.assertEqual(both_fail["summary"]["verdict"], "failed_checks")
        self.assertFalse(s.check_answer("FAILED", {"not_contains": ["FAILED"]})[0]["passed"])

    def test_checkpoints_interrupt_and_separate_judge(self):
        checkpoints = []
        with patch.object(s, "invoke", side_effect=[{"text": "baseline"}, KeyboardInterrupt()]):
            report = self.evaluate(checkpoint=lambda r: checkpoints.append(copy.deepcopy(r)))
        self.assertEqual(report["status"], "interrupted")
        self.assertEqual(report["summary"]["verdict"], "incomplete")
        self.assertEqual(len(report["cases"][0]["trials"][0]["answers"]), 1)
        self.assertEqual(checkpoints[0]["status"], "running")
        with patch.object(s, "invoke", side_effect=good_adapter) as invoke:
            self.evaluate(judge_adapter="judge")
        self.assertEqual([c.args[0] for c in invoke.call_args_list], ["unused", "unused", "judge", "judge"])


class ProcessAndCLITests(unittest.TestCase):
    def test_cleanup_permission_race_preserves_error_and_reaps_child(self):
        for exited in (True, False):
            child = Mock(pid=123, returncode=0 if exited else None)
            child.poll.return_value = child.returncode
            with patch.object(s.subprocess, "Popen", return_value=child), \
                    patch.object(s.os, "fstat", return_value=Mock(st_size=s.MAX_BYTES + 1)), \
                    patch.object(s.os, "killpg", side_effect=PermissionError):
                expected = "adapter_output_too_large" if exited else "adapter_cleanup_failed"
                with self.assertRaisesRegex(s.AdapterError, expected):
                    s.process(["unused"], "", 1)
            child.wait.assert_called_once()
            self.assertEqual(child.kill.call_count, 0 if exited else 1)

    def test_protocol_failures_and_output_bound(self):
        programs = [("print('[]')", "adapter_response_not_object"),
                    ("print('bad')", "adapter_invalid_json"),
                    ("print('{\"metadata\": NaN}')", "adapter_invalid_json"),
                    ("print('{\"metadata\": []}')", "adapter_metadata_not_object"),
                    ("import sys; sys.exit(7)", "adapter_exit_7"),
                    ("import time; time.sleep(5)", "adapter_timeout"),
                    ("print('x' * 5000000)", "adapter_output_too_large")]
        for program, code in programs:
            command = shlex.join([sys.executable, "-c", program])
            with self.assertRaisesRegex(s.AdapterError, code):
                s.invoke(command, {}, 0.2 if "sleep" in program else 3)

    def test_cli_forward_reverse_tie_private_report_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as directory:
            for mode, old, new, expected in (("forward", "old", "new", 0), ("reverse", "new", "old", 2), ("tie", "new", "new", 3)):
                target = Path(directory) / (mode + ".json")
                command = [sys.executable, str(ROOT / "volna_skillcheck.py"), "--old", str(ROOT / f"examples/{old}.md"),
                           "--new", str(ROOT / f"examples/{new}.md"), "--cases", str(ROOT / "examples/cases.json"),
                           "--adapter", shlex.join([sys.executable, str(ROOT / "examples/mock_adapter.py")]), "--out", str(target)]
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stderr + result.stdout)
                report = json.loads(target.read_text())
                self.assertEqual(report["status"], "completed")
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)
                before = target.read_bytes()
                self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
                self.assertEqual(target.read_bytes(), before)

    def test_atomic_write_preserves_previous_report_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "report.json"
            s.write_report(target, {"first": True})
            with patch.object(s.os, "replace", side_effect=OSError("disk")):
                with self.assertRaises(OSError):
                    s.write_report(target, {"second": True})
            self.assertEqual(json.loads(target.read_text()), {"first": True})
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_timeout_kills_descendants(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "escaped"
            child = f"import time; from pathlib import Path; time.sleep(.5); Path({str(marker)!r}).touch()"
            program = f"import subprocess,sys,time; subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(10)"
            with self.assertRaisesRegex(s.AdapterError, "adapter_timeout"):
                s.process([sys.executable, "-c", program], "", .2)
            import time
            time.sleep(.6)
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
