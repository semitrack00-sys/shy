import asyncio
import json
import sys
import types
import unittest
from intelligence_helpers import ROOT

sys.path.insert(0, str(ROOT / "services" / "core"))
package = types.ModuleType("agent_runtime")
package.__path__ = [str(ROOT / "services" / "agent-runtime")]
sys.modules["agent_runtime"] = package

from fastapi import FastAPI
from fastapi.testclient import TestClient
from intelligence_api import IntelligenceBodyLimit, router


app = FastAPI()
app.include_router(router)
app.add_middleware(IntelligenceBodyLimit)
client = TestClient(app)


class ApiTests(unittest.TestCase):
    def test_every_documented_handler_is_reachable_through_http(self):
        examples = json.loads((ROOT / "docs" / "examples" / "intelligence-v100.json").read_text())
        self.assertEqual(len(examples), 50)
        for example in examples:
            with self.subTest(capability=example["capability"]):
                response = client.post("/intelligence/evaluate", json=example)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["boundary"], "EVALUATED")
                self.assertFalse(response.json()["side_effect_performed"])

    def test_catalog_fifty_bounded_capabilities(self):
        response = client.get("/intelligence/capabilities")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["capability_count"], 50)
        self.assertFalse(response.json()["scope_authenticated"])

    def test_valid_numeric_evaluation(self):
        response = client.post("/intelligence/evaluate", json={"capability": "descriptive_stats", "payload": {"values": [1, 2, 3]}})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["payload"]["mean"], 2)
        self.assertFalse(response.json()["side_effect_performed"])

    def test_unknown_404_missing_domain_input_422(self):
        self.assertEqual(client.post("/intelligence/evaluate", json={"capability": "shell", "payload": {}}).status_code, 404)
        self.assertEqual(client.post("/intelligence/evaluate", json={"capability": "chunk_text", "payload": {}}).status_code, 422)

    def test_envelope_is_strict_and_forbids_unknown_fields(self):
        for body in [{"capability": 1, "payload": {}}, {"capability": "chunk_text", "payload": []}, {"capability": "chunk_text", "payload": {}, "execute": True}]:
            self.assertEqual(client.post("/intelligence/evaluate", json=body).status_code, 422)

    def test_malformed_json(self):
        self.assertEqual(client.post("/intelligence/evaluate", content='{bad', headers={"content-type": "application/json"}).status_code, 422)

    def test_deep_nonfinite_and_invalid_utf8_json_rejected(self):
        for body in [b"[" * 2000 + b"0" + b"]" * 2000, b'{"capability":"latency_report","payload":{"values":[NaN]}}', b'\xff']:
            self.assertEqual(client.post("/intelligence/evaluate", content=body, headers={"content-type": "application/json"}).status_code, 422)

    def test_oversized_body_before_parse_including_trailing_slash(self):
        for path in ["/intelligence/evaluate", "/intelligence/evaluate/", "/intelligence/batch"]:
            self.assertEqual(client.post(path, content=b"x" * 262145).status_code, 413)

    def test_batch_preserves_individual_failure_and_enforces_count(self):
        good = {"capability": "latency_report", "payload": {"values": [10, 20]}}
        bad = {"capability": "shell", "payload": {}}
        response = client.post("/intelligence/batch", json={"requests": [good, bad]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["all_evaluated"])
        self.assertEqual([x["boundary"] for x in response.json()["results"]], ["EVALUATED", "UNAVAILABLE"])
        self.assertEqual(client.post("/intelligence/batch", json={"requests": [good] * 11}).status_code, 422)

    def test_streamed_body_without_content_length(self):
        sent = []
        chunks = iter([{"type": "http.request", "body": b"x" * 150000, "more_body": True}, {"type": "http.request", "body": b"x" * 150000, "more_body": False}])
        async def receive():
            return next(chunks)
        async def send(message):
            sent.append(message)
        async def unreachable(*args):
            self.fail("oversized body reached JSON parser")
        asyncio.run(IntelligenceBodyLimit(unreachable)({"type": "http", "method": "POST", "path": "/intelligence/evaluate", "headers": []}, receive, send))
        self.assertEqual(sent[0]["status"], 413)

    def test_openapi_exposes_request_contracts(self):
        schema = client.get("/openapi.json").json()
        self.assertIn("/intelligence/evaluate", schema["paths"])
        self.assertFalse(schema["components"]["schemas"]["EvaluationRequest"]["additionalProperties"])


if __name__ == "__main__":
    unittest.main()
