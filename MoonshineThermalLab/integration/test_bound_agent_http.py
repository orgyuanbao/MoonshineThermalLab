"""Exercise the research controller and Chat Completions transport over loopback HTTP."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from integration.bound_agent import get_local_checker, run_agent
from integration.residual_tool import TOOL_NAME


FAKE_KEY = "local-fixture-token-for-tests"
FAKE_MODEL = "loopback-math-fixture"
GOAL = "Check the weak signed bound, then use the witness to choose a replacement."


def model_reply(content, candidate=None, call_id=None):
    message = {"role": "assistant", "content": content}
    if candidate is not None:
        message["tool_calls"] = [{
            "id": call_id, "type": "function",
            "function": {"name": TOOL_NAME, "arguments": json.dumps({"candidate": candidate})},
        }]
    return {"choices": [{"index": 0, "message": message, "finish_reason": "tool_calls" if candidate else "stop"}]}


def respond_to_evidence(request):
    outputs = [json.loads(m["content"]) for m in request["messages"] if m["role"] == "tool"]
    if not outputs:
        return 200, model_reply("Test the first conjecture.", "weak_signed", "weak-call")
    if len(outputs) == 1 and outputs[-1]["status"] == "counterexample":
        return 200, model_reply("The witness refutes the shortcut. Check the envelope.",
                                "block_two_endpoint", "corrected-call")
    if len(outputs) == 2 and outputs[-1]["status"] == "no_counterexample_in_domain":
        return 200, model_reply("The corrected conjecture survived the finite search.")
    return 400, {"error": "Unexpected previous tool evidence"}


@contextmanager
def local_service(responder=respond_to_evidence):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append({"path": self.path, "authenticated": self.headers.get("Authorization") == "Bearer " + FAKE_KEY,
                             "json": body})
            status, result = responder(body)
            output = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(output)))
            self.end_headers()
            self.wfile.write(output)

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.03}, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/v1", requests
        finally:
            server.shutdown()
            thread.join(3)


@contextmanager
def isolated_configuration():
    # Keep real model settings out of fixtures, including developer machines with inherited .env values.
    with patch.dict(os.environ, {}, clear=False):
        for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
            os.environ.pop(name, None)
        yield


def configured_policy(folder, url):
    from integration.bound_agent_model import load_settings, make_model_policy
    cfg = folder / ".env"
    cfg.write_text(f"LLM_BASE_URL={url}\nLLM_API_KEY={FAKE_KEY}\nLLM_MODEL={FAKE_MODEL}\n", encoding="utf-8")
    return make_model_policy(load_settings(cfg))


def fixture_receipt():
    """Return reproducible public evidence from a scripted HTTP peer and the real project checker."""
    with TemporaryDirectory() as directory, isolated_configuration(), local_service() as (url, requests):
        folder = Path(directory)
        policy = configured_policy(folder, url)
        report = run_agent(policy, get_local_checker(folder/"home"), goal=GOAL)
    exchanges = []
    for entry in requests:
        body = entry["json"]
        messages = body["messages"]
        answers = []
        for message in messages:
            if message["role"] == "tool":
                answers.append({"call_id": message["tool_call_id"], "result": json.loads(message["content"])})
        exchanges.append({
            "path": entry["path"], "bearer_header_matched_fixture": entry["authenticated"],
            "model": body["model"], "tools": [t["function"]["name"] for t in body["tools"]],
            "candidate_values": body["tools"][0]["function"]["parameters"]["properties"]["candidate"]["enum"],
            "roles": [m["role"] for m in messages],
            "assistant_call_ids": [t["id"] for m in messages for t in m.get("tool_calls", [])],
            "returned_tool_messages": answers,
        })
    return {"origin": "scripted loopback HTTP peer with actual Moonshine tool dispatch",
            "external_model_calls": 0, "http_requests": exchanges, "controller_result": report}


class BoundAgentHTTPTests(unittest.TestCase):
    def test_auth_schema_and_actual_observations_round_trip(self):
        receipt = fixture_receipt()
        requests = receipt["http_requests"]
        self.assertEqual(receipt["controller_result"]["status"], "finite_search_completed")
        self.assertEqual([req["roles"] for req in requests], [
            ["system", "user"], ["system", "user", "assistant", "tool"],
            ["system", "user", "assistant", "tool", "assistant", "tool"],
        ])
        for req in requests:
            self.assertEqual(req["path"], "/v1/chat/completions")
            self.assertTrue(req["bearer_header_matched_fixture"])
            self.assertEqual(req["model"], FAKE_MODEL)
            self.assertEqual(req["tools"], [TOOL_NAME])
            self.assertIn("block_two_endpoint", req["candidate_values"])
            self.assertEqual(req["assistant_call_ids"], [m["call_id"] for m in req["returned_tool_messages"]])
        history = receipt["controller_result"]["history"]
        self.assertEqual(requests[1]["returned_tool_messages"][0]["result"], history[0]["result"])
        self.assertEqual([m["result"] for m in requests[2]["returned_tool_messages"]], [s["result"] for s in history])
        self.assertEqual(history[0]["result"]["witness"]["true_error_inf"], "399/538")
        self.assertEqual(history[1]["result"]["checked_cases"], 1296)
        self.assertNotIn(FAKE_KEY, json.dumps(receipt))

    def test_blank_configuration_fails_before_any_http_request(self):
        from integration.bound_agent_model import load_settings, make_model_policy
        with TemporaryDirectory() as directory, isolated_configuration(), local_service() as (url, requests):
            config = Path(directory) / ".env"
            config.write_text(f"LLM_BASE_URL={url}\nLLM_API_KEY=\nLLM_MODEL=\n", encoding="utf-8")
            with self.assertRaises((ValueError, RuntimeError)):
                make_model_policy(load_settings(config))(GOAL, [])
            self.assertEqual(requests, [])

    def test_duplicate_config_and_credential_bearing_endpoint_are_rejected_locally(self):
        from integration.bound_agent_model import load_settings
        with TemporaryDirectory() as directory, isolated_configuration(), local_service() as (url, requests):
            config = Path(directory) / ".env"
            for base, extra in ((url, f"LLM_API_KEY={FAKE_KEY}\n"),
                                (url + "?token=PRIVATE_QUERY_MARKER", "")):
                config.write_text(f"LLM_BASE_URL={base}\nLLM_API_KEY={FAKE_KEY}\n"
                                  f"LLM_MODEL={FAKE_MODEL}\n{extra}", encoding="utf-8")
                with self.subTest(extra=bool(extra)), self.assertRaises(ValueError) as caught:
                    load_settings(config)
                self.assertNotIn(FAKE_KEY, str(caught.exception))
                self.assertNotIn("PRIVATE_QUERY_MARKER", str(caught.exception))
            self.assertEqual(requests, [])

    def test_error_response_cannot_echo_secrets_into_agent_record(self):
        def denied(_request):
            return 401, {"error": {"message": "Private service output with " + FAKE_KEY + " / PRIVATE_BODY_MARKER"}}

        with TemporaryDirectory() as directory, isolated_configuration(), local_service(denied) as (url, requests):
            folder = Path(directory)
            policy = configured_policy(folder, url)
            run = run_agent(policy, get_local_checker(folder/"home"), goal=GOAL)
        self.assertEqual(len(requests), 1)
        self.assertEqual(run["status"], "error")
        self.assertEqual(run["history"], [])
        self.assertIn("401", run["reason"])
        self.assertNotIn(FAKE_KEY, json.dumps(run))
        self.assertNotIn("PRIVATE_BODY_MARKER", json.dumps(run))

    def test_multiple_calls_do_not_execute_in_sequential_controller(self):
        def ambiguous(_request):
            envelope = model_reply("Two incompatible actions.", "weak_signed", "call-a")
            envelope["choices"][0]["message"]["tool_calls"] += [
                {"id":"call-b", "type":"function", "function":{"name":TOOL_NAME, "arguments":'{"candidate":"block_signed"}'}}]
            return 200, envelope

        with TemporaryDirectory() as directory, isolated_configuration(), local_service(ambiguous) as (url, requests):
            folder = Path(directory)
            run = run_agent(configured_policy(folder, url), get_local_checker(folder/"home"), goal=GOAL)
        self.assertEqual(len(requests), 1)
        self.assertEqual(run["status"], "error")
        self.assertEqual(run["history"], [])


if __name__ == "__main__":
    unittest.main()
