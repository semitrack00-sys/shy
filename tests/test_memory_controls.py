import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/core"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import memory_controls as controls


class MemoryControlContracts(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(controls.router); app.add_middleware(controls.MemoryBodyLimit)
        self.client = TestClient(app)
        self.body = {"subject_key": "project.shy.database", "content": "SHY uses PostgreSQL.", "confirmed": True}

    def test_confirmation_scope_secrets_and_bounds_rejected_before_database(self):
        with patch.object(controls.memory, "connect") as connect:
            for patch_value in [{"confirmed": False}, {"confirmed": 1}, {"confirmed": "true"},
                                {"user_id": str(uuid.uuid4())}, {"content": "my password is example"},
                                {"content": " "}, {"content": "x" * 501}, {"category": "TASK_OUTCOME"},
                                {"subject_key": "Upper case"}, {"subject_key": "user.password"}]:
                response = self.client.post("/memories", json={**self.body, **patch_value})
                self.assertEqual(response.status_code, 422, patch_value)
            self.assertEqual(self.client.post("/memories", json={"subject_key": "test", "content": "Fact"}).status_code, 422)
            self.assertEqual(self.client.post("/memories", content="[" * 2000 + "]" * 2000).status_code, 422)
            self.assertEqual(self.client.post("/memories", content="x" * 8193).status_code, 413)
            connect.assert_not_called()

    def test_database_error_does_not_expose_credentials(self):
        with patch.object(controls.memory, "connect", side_effect=RuntimeError("postgres://user:secret@private")):
            for response in [self.client.get("/memories"), self.client.post("/memories", json=self.body)]:
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["detail"], "memory_database_unavailable")
                self.assertNotIn("private", response.text)

    def test_revision_detects_content_status_change_but_not_retrieval_counters(self):
        row = {"memory_id": uuid.uuid4(), "category": "PROJECT", "subject_key": "project.shy.database",
               "content": "SHY uses PostgreSQL.", "status": "ACTIVE", "use_count": 1,
               "updated_at": datetime.now(timezone.utc)}
        expected = controls.revision(row)
        self.assertEqual(expected, controls.revision({**row, "use_count": 50, "updated_at": None}))
        self.assertNotEqual(expected, controls.revision({**row, "content": "SHY uses another database."}))
        self.assertNotEqual(expected, controls.revision({**row, "status": "SUPERSEDED"}))


if __name__ == "__main__":
    unittest.main()
