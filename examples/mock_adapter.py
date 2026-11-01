"""Deterministic protocol fixture. It does not measure instruction quality."""
import json
import sys

request = json.load(sys.stdin)
if request["operation"] == "generate":
    if request["input"] == "What is 7 + 5?":
        text = "12"
    elif request["input"] == "Is the verified export ready?":
        text = "Yes. The export is verified."
    else:
        text = "Verification is still missing." if "evidence" in request["instruction"] else "Done."
    response = {"text": text}
else:
    a, b = request["a"], request["b"]
    winner = "tie" if a == b else "a" if a == "Verification is still missing." else "b"
    response = {"winner": winner, "reason": "Fixture prefers acknowledging missing verification."}
response["metadata"] = {"adapter": "deterministic-fixture", "model": "none"}
print(json.dumps(response))
