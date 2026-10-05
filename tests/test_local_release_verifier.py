"""HTTP fixtures test the verifier, not SHY's model or database implementation."""
import importlib.util
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("local_release_verifier", ROOT / "scripts/verify_local_release.py")
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)
EXAMPLES = ROOT / "docs/examples/intelligence-v100.json"
NAMES = [item["capability"] for item in json.loads(EXAMPLES.read_text())]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        mode = self.server.mode
        if self.path == "/health":
            self.respond({"version": "0.50.0" if mode == "old" else "0.105.0",
                          "database_connected": mode != "database",
                          "ollama_connected": False, "local_model_available": False})
        elif self.path == "/platform/capabilities":
            self.respond({"version": "0.105.0", "platform": {"sequence_complete": True,
                          "required_disabled_invariants_hold": mode != "invariants"}})
        elif self.path == "/intelligence/capabilities":
            self.respond({"capability_count": 50, "external_execution": False,
                          "capabilities": [{"capability_id": name} for name in
                                           (NAMES[:-1] if mode == "catalog" else NAMES)]})
        else:
            self.respond({}, 404)

    def do_POST(self):
        size = int(self.headers["Content-Length"])
        raw = self.rfile.read(size)
        if size > 256 * 1024:
            return self.respond({}, 413)
        item = json.loads(raw)
        if self.path == "/intelligence/batch":
            return self.respond({"all_evaluated": True, "results": [{}] * 10, "side_effect_performed": False})
        if item["capability"] == "shell":
            return self.respond({}, 404)
        if item["payload"].get("values") == "invalid":
            return self.respond({}, 422)
        self.respond({"boundary": "EVALUATED", "capability": item["capability"],
                      "side_effect_performed": self.server.mode == "side_effect"})


class LocalVerifierTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.mode = "good"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_all_examples_and_failure_boundaries(self):
        report = verifier.verify(self.url, EXAMPLES, wait_seconds=0)
        self.assertEqual(report["utility_examples_passed"], 50)
        self.assertFalse(report["local_model_available"])
        self.assertFalse(report["model_inference_tested"])

    def test_rejects_old_release_disconnected_db_and_invariants(self):
        for mode in ("old", "database", "invariants", "catalog", "side_effect"):
            with self.subTest(mode=mode):
                self.server.mode = mode
                with self.assertRaises(verifier.VerificationError):
                    verifier.verify(self.url, EXAMPLES, wait_seconds=0)

    def test_model_requirement_is_explicit(self):
        with self.assertRaisesRegex(verifier.VerificationError, "Ollama"):
            verifier.verify(self.url, EXAMPLES, wait_seconds=0, require_model=True)

    def test_refuses_remote_and_credential_urls(self):
        for url in ("https://example.com", "http://example.com", "http://user:secret@localhost:8000",
                    self.url + "/nested", self.url + "?token=secret"):
            with self.subTest(url=url), self.assertRaises(verifier.VerificationError):
                verifier.verify(url, EXAMPLES, wait_seconds=0)


if __name__ == "__main__":
    unittest.main()
