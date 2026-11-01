"""Compare instruction revisions on recorded tasks with a blind, swapped judge."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import random
import shlex
import signal
import subprocess
import sys
import tempfile
import time

__version__ = "0.3.1"
EXIT_CODES = {"candidate_improvement": 0, "incomplete": 1, "regression": 2,
              "failed_checks": 2, "inconclusive": 3, "insufficient_data": 3}
MAX_BYTES = 4 * 1024 * 1024


class AdapterError(Exception):
    """A diagnostic code safe to store without leaking process output or arguments."""


def decode_json(raw):
    def invalid_constant(value):
        raise ValueError("JSON must not contain NaN or Infinity")
    return json.loads(raw, parse_constant=invalid_constant)


def process(command, payload, timeout, *, cwd=None, isolate=True, env=None):
    """Bound output and terminate the process group on timeout or interruption."""
    with tempfile.TemporaryFile() as source, tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        source.write(payload.encode("utf-8"))
        source.seek(0)
        try:
            child = subprocess.Popen(command, stdin=source, stdout=out, stderr=err,
                                     cwd=cwd, start_new_session=isolate,
                                     env={**(os.environ if env is None else env), "_VOLNA_SKILLCHECK_MANAGED": "1"})
        except OSError as error:
            raise AdapterError("adapter_start_failed") from error
        deadline = time.monotonic() + timeout
        try:
            while True:
                if max(os.fstat(out.fileno()).st_size, os.fstat(err.fileno()).st_size) > MAX_BYTES:
                    raise AdapterError("adapter_output_too_large")
                if child.poll() is not None:
                    break
                if time.monotonic() >= deadline:
                    raise AdapterError("adapter_timeout")
                time.sleep(0.02)
            if child.returncode:
                raise AdapterError(f"adapter_exit_{child.returncode}")
            out.seek(0)
            try:
                return out.read(MAX_BYTES).decode("utf-8")
            except UnicodeDecodeError as error:
                raise AdapterError("adapter_invalid_utf8") from error
        finally:
            # Descendants may outlive their parent, including after a successful exit.
            try:
                if isolate:
                    os.killpg(child.pid, signal.SIGKILL)
                else:
                    child.kill()
            except ProcessLookupError:
                pass
            except PermissionError:
                # macOS can reject killpg when the group contains an exited child.
                if child.poll() is None:
                    child.kill()
                    raise AdapterError("adapter_cleanup_failed")
            finally:
                child.wait()


def invoke(command, request, timeout):
    raw = process(shlex.split(command), json.dumps(request, ensure_ascii=False), timeout)
    try:
        result = decode_json(raw)
    except ValueError as error:
        raise AdapterError("adapter_invalid_json") from error
    if not isinstance(result, dict):
        raise AdapterError("adapter_response_not_object")
    if not isinstance(result.get("metadata", {}), dict):
        raise AdapterError("adapter_metadata_not_object")
    return result


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(old, new, cases, adapter, judge_adapter, timeout, repeats, min_wins):
    if not all(nonempty(x) for x in (old, new, adapter, judge_adapter)):
        raise ValueError("Instructions and adapter commands must be nonempty strings")
    if not shlex.split(adapter) or not shlex.split(judge_adapter):
        raise ValueError("Adapter commands must contain an executable")
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if any(type(x) is not int or x < 1 for x in (repeats, min_wins)):
        raise ValueError("repeats and min-wins must be positive integers")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Cases must be a nonempty JSON array")
    ids = set()
    for case in cases:
        if not isinstance(case, dict) or any(not nonempty(case.get(k)) for k in ("id", "input", "criteria")):
            raise ValueError("Each case needs nonempty string id, input, and criteria")
        if case.keys() - {"id", "input", "criteria", "context", "checks"}:
            raise ValueError("Unknown case field; allowed: id, input, criteria, context, checks")
        if case["id"] in ids:
            raise ValueError("Case IDs must be unique")
        ids.add(case["id"])
        if not isinstance(case.get("context", ""), str):
            raise ValueError("Case context must be a string")
        checks = case.get("checks", {})
        if not isinstance(checks, dict) or checks.keys() - {"contains", "not_contains"}:
            raise ValueError("checks supports contains and not_contains")
        for values in checks.values():
            if not isinstance(values, list) or not all(nonempty(v) for v in values):
                raise ValueError("Each check must be a list of nonempty strings")


def check_answer(text, checks):
    return [{"kind": kind, "value": value,
             "passed": (value in text) == (kind == "contains")}
            for kind, values in checks.items() for value in values]


def combine(outcomes):
    # A regression in one trial cannot be outvoted by repeated wins.
    if "old" in outcomes:
        return "old"
    if "abstain" in outcomes:
        return "abstain"
    return outcomes[0] if len(set(outcomes)) == 1 else "unstable"


def summarize(rows, min_wins, complete):
    counts = Counter(row.get("better") for row in rows)
    errors = sum(row["status"] == "error" for row in rows)
    failures = sum(any(not c["passed"] for t in row["trials"]
                       for c in t["checks"].get("new", [])) for row in rows)
    verdict = ("incomplete" if errors or not complete else
               "regression" if counts["old"] else
               "failed_checks" if failures else
               "inconclusive" if counts["abstain"] or counts["unstable"] else
               "insufficient_data" if 0 < counts["new"] < min_wins else
               "candidate_improvement" if counts["new"] else "inconclusive")
    return {**{k: counts[k] for k in ("old", "new", "tie", "abstain", "unstable")},
            "errors": errors, "failed_check_cases": failures, "verdict": verdict}


def digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run(old, new, cases, adapter, seed=0, timeout=120, *, judge_adapter=None,
        repeats=1, min_wins=5, checkpoint=None):
    judge_adapter = judge_adapter or adapter
    validate(old, new, cases, adapter, judge_adapter, timeout, repeats, min_wins)
    rng = random.Random(seed)
    rows = []
    report = {"schema_version": 2, "volna_skillcheck_version": __version__,
              "created_at": datetime.now(timezone.utc).isoformat(), "status": "running",
              "seed": seed, "config": {"repeats": repeats, "min_wins": min_wins, "timeout": timeout,
                  "adapter_sha256": digest(adapter), "judge_adapter_sha256": digest(judge_adapter)},
              "instructions": {"old": old, "new": new},
              "instruction_hashes": {"old": digest(old), "new": digest(new)},
              "suite_sha256": digest(json.dumps(cases, sort_keys=True, ensure_ascii=False)),
              "suite": cases, "cases": rows}

    def save():
        report["summary"] = summarize(rows, min_wins, report["status"] == "completed")
        if checkpoint:
            checkpoint(report)

    save()
    try:
        for case in cases:
            row = {"id": case["id"], "status": "running", "trials": []}
            rows.append(row)
            for trial_index in range(repeats):
                trial = {"trial": trial_index + 1, "answers": {}, "checks": {},
                         "generation_metadata": {}, "judgments": [], "status": "running"}
                row["trials"].append(trial)
                stage = "generate"
                try:
                    order = ["old", "new"]
                    rng.shuffle(order)
                    trial["generation_order"] = order[:]
                    for version in order:
                        stage = "generate_" + version
                        response = invoke(adapter, {"operation": "generate", "instruction": report["instructions"][version],
                            "input": case["input"], "context": case.get("context", "")}, timeout)
                        if not isinstance(response, dict) or not nonempty(response.get("text")):
                            raise AdapterError("generation_invalid_response")
                        trial["answers"][version] = response["text"]
                        trial["generation_metadata"][version] = response.get("metadata", {})
                        trial["checks"][version] = check_answer(response["text"], case.get("checks", {}))
                        save()
                    outcomes = []
                    order = ["old", "new"]
                    rng.shuffle(order)
                    identical = trial["answers"]["old"] == trial["answers"]["new"]
                    if identical:
                        outcomes = ["tie", "tie"]
                        trial["judge_skipped"] = "identical_answers"
                    for presentation in (() if identical else (order, order[::-1])):
                        stage = "judge_" + str(len(trial["judgments"]) + 1)
                        response = invoke(judge_adapter, {"operation": "judge", "input": case["input"],
                            "context": case.get("context", ""), "criteria": case["criteria"],
                            "a": trial["answers"][presentation[0]], "b": trial["answers"][presentation[1]]}, timeout)
                        if (not isinstance(response, dict) or response.get("winner") not in ("a", "b", "tie", "abstain")
                                or not nonempty(response.get("reason"))):
                            raise AdapterError("judge_invalid_response")
                        winner = response["winner"]
                        better = presentation[0 if winner == "a" else 1] if winner in ("a", "b") else winner
                        outcomes.append(better)
                        trial["judgments"].append({"presentation_order": presentation, "winner": winner,
                            "better": better, "reason": response["reason"], "metadata": response.get("metadata", {})})
                        save()
                    # Swapped disagreement is uncertainty, never an established win/loss.
                    better = outcomes[0] if outcomes[0] == outcomes[1] else "unstable"
                    if "abstain" in outcomes:
                        better = "abstain"
                    passes = {v: all(c["passed"] for c in trial["checks"][v]) for v in ("old", "new")}
                    if passes["old"] and not passes["new"]:
                        better = "old"
                    trial.update(status="evaluated", better=better)
                except (AdapterError, OSError, ValueError, subprocess.SubprocessError) as error:
                    trial.update(status="error", stage=stage,
                                 error=str(error) if isinstance(error, AdapterError) else type(error).__name__)
                save()
            row["status"] = "error" if any(t["status"] == "error" for t in row["trials"]) else "evaluated"
            evaluated = [t["better"] for t in row["trials"] if "better" in t]
            if evaluated:
                row["better"] = combine(evaluated)
            save()
        report["status"] = "completed"
    except KeyboardInterrupt:
        report["status"] = "interrupted"
        if rows and rows[-1]["status"] == "running":
            rows[-1]["status"] = "error"
            rows[-1]["trials"][-1].update(status="error", error="interrupted")
    save()
    return report


def write_report(target, report):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as file:
            temporary = Path(file.name)
            json.dump(report, file, ensure_ascii=False, indent=2, allow_nan=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def read_input(path):
    with Path(path).open("rb") as file:
        data = file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Input file exceeds 4 MiB")
    return data.decode("utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    for name in ("old", "new", "cases", "adapter", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--judge-adapter", help="Separate judge command; defaults to --adapter")
    parser.add_argument("--seed", type=int, default=0, help="Presentation/generation order seed, not a model seed")
    parser.add_argument("--timeout", type=float, default=120, help="Seconds per adapter call")
    parser.add_argument("--repeats", type=int, default=1, help="Independent generations per case")
    parser.add_argument("--min-wins", type=int, default=5, help="Distinct winning cases required for candidate improvement")
    args = parser.parse_args(argv)
    try:
        old, new = read_input(args.old), read_input(args.new)
        cases = decode_json(read_input(args.cases))
        validate(old, new, cases, args.adapter, args.judge_adapter or args.adapter,
                 args.timeout, args.repeats, args.min_wins)
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Reserve before spending on model calls; never overwrite inputs or prior reports.
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
        print(f"Evaluating {len(cases)} cases, {args.repeats} trial(s), up to {4 * len(cases) * args.repeats} adapter calls.", file=sys.stderr)
        report = run(old, new, cases, args.adapter, args.seed, args.timeout,
                     judge_adapter=args.judge_adapter, repeats=args.repeats, min_wins=args.min_wins,
                     checkpoint=lambda report: write_report(target, report))
    except (OSError, ValueError) as error:
        # JSON decode errors may embed private data; don't echo exception messages.
        print(f"volna-skillcheck: {type(error).__name__}; check input schema, paths, options, and that --out does not exist.", file=sys.stderr)
        return 1
    print(json.dumps(report["summary"]))
    return 130 if report["status"] == "interrupted" else EXIT_CODES[report["summary"]["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
