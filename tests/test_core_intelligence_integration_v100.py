"""Exercise the actual SHY app and DB startup without claiming model inference."""
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("shy_core_v100", ROOT / "services" / "core" / "main.py")
main = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = main
spec.loader.exec_module(main)

from fastapi.testclient import TestClient


class CoreIntegrationTests(unittest.TestCase):
    def test_core_startup_manifest_and_pipeline(self):
        with TestClient(main.app) as client:
            manifest = client.get("/platform/capabilities").json()
            self.assertEqual(manifest["version"], main.SHY_VERSION)
            self.assertTrue(manifest["platform"]["sequence_complete"])
            self.assertTrue(manifest["platform"]["required_disabled_invariants_hold"])
            self.assertEqual(client.get("/intelligence/capabilities").json()["capability_count"], 50)
            response = client.post("/intelligence/evaluate", json={"capability": "evidence_pipeline", "payload": {"query": "solar kit", "scope": "user-a", "now": "2026-10-05T00:00:00Z", "passages": [{"id": "p1", "scope": "user-a", "source_id": "doc1", "observed_at": "2026-10-05T00:00:00Z", "text": "solar kit costs 100 USD"}, {"id": "foreign", "scope": "user-b", "source_id": "private", "observed_at": "2026-10-05T00:00:00Z", "text": "solar kit confidential"}]}})
            self.assertEqual(response.status_code, 200, response.text)
            result = response.json()["payload"]
            self.assertEqual(result["boundary"], "EVIDENCE_AVAILABLE")
            self.assertEqual(result["citation_ids"], ["p1"])
            self.assertNotIn("confidential", result["context"])
            self.assertFalse(result["answer_generated"])
            self.assertIn("/chat", client.get("/openapi.json").json()["paths"])
            self.assertEqual(client.post("/intelligence/evaluate", json={"capability": "shell", "payload": {}}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
