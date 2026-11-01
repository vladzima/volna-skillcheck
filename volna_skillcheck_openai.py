"""Evaluate through an OpenAI-compatible Chat Completions endpoint."""
import ipaddress
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

from volna_skillcheck import AdapterError, MAX_BYTES, __version__, decode_json, digest, nonempty
from volna_skillcheck_adapter import adapter_main, adapter_parser, prepare, validate_result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward provider credentials to a redirect destination.
        raise AdapterError("api_redirect_refused")


def endpoint(base_url):
    url = urllib.parse.urlsplit(base_url)
    loopback = url.hostname == "localhost"
    try:
        loopback = loopback or ipaddress.ip_address(url.hostname or "").is_loopback
    except ValueError:
        pass
    if (not url.hostname or url.username or url.password or url.query or url.fragment
            or url.scheme not in ("http", "https") or (url.scheme == "http" and not loopback)):
        raise ValueError("Use HTTPS, or HTTP on loopback, without credentials/query/fragment")
    return base_url.rstrip("/") + "/chat/completions", loopback


def evaluate(request, model, timeout=90, base_url="https://api.openai.com/v1",
             api_key_env="OPENAI_API_KEY", response_format="json_object", temperature=None):
    instructions, prompt, schema = prepare(request)
    target, loopback = endpoint(base_url)
    key = os.environ.get(api_key_env, "")
    if not key and not loopback:
        raise AdapterError("api_key_missing")
    body = {"model": model, "messages": [{"role": "system", "content": instructions},
                                          {"role": "user", "content": prompt}], "stream": False}
    if response_format == "json_schema":
        body["response_format"] = {"type": "json_schema", "json_schema": {
            "name": "skillcheck_response", "strict": True, "schema": schema}}
    elif response_format == "json_object":
        body["response_format"] = {"type": "json_object"}
    elif response_format != "text":
        raise ValueError("Invalid response format")
    if temperature is not None:
        if not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError("Temperature must be between zero and two")
        body["temperature"] = temperature
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + key
    call = urllib.request.Request(target, data=json.dumps(body).encode(), headers=headers, method="POST")
    try:
        with urllib.request.build_opener(NoRedirect).open(call, timeout=timeout) as response:
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        error.close()
        raise AdapterError(f"api_http_{error.code}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise AdapterError("api_connection_failed") from error
    if len(raw) > MAX_BYTES:
        raise AdapterError("api_response_too_large")
    try:
        envelope = decode_json(raw)
        choice = envelope["choices"][0]
        message = choice["message"]
        if choice.get("finish_reason") != "stop":
            raise AdapterError("api_incomplete_response")
        if message.get("tool_calls") or message.get("function_call") or message.get("refusal"):
            raise AdapterError("api_unexpected_response")
        if not nonempty(message.get("content")):
            raise AdapterError("api_empty_response")
        result = validate_result(decode_json(message["content"]), request["operation"])
    except (KeyError, IndexError, TypeError, ValueError, AttributeError) as error:
        raise AdapterError("api_invalid_response") from error
    result["metadata"] = {"adapter": "volna-skillcheck-openai", "adapter_version": __version__,
        "model": model, "resolved_model": envelope.get("model"), "base_url_sha256": digest(base_url),
        "response_format": response_format, "temperature": temperature,
        "instructions_sha256": digest(instructions), "prompt_sha256": digest(prompt),
        "usage": envelope.get("usage"), "system_fingerprint": envelope.get("system_fingerprint")}
    return result


def main(argv=None):
    parser = adapter_parser(__doc__)
    parser.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    parser.add_argument("--api-key-env", default="OPENAI_API_KEY", help="Environment variable name, never the key itself")
    parser.add_argument("--response-format", choices=("json_object", "json_schema", "text"), default="json_object")
    parser.add_argument("--temperature", type=float, help="Omitted by default for provider/model compatibility")
    return adapter_main(parser, evaluate, argv)


if __name__ == "__main__":
    sys.exit(main())
