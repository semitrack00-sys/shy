"""Real PostgreSQL persistence, stale-review, pagination and local-user boundaries."""
import os
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "services/core"))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import memory
import memory_controls


@unittest.skipUnless(os.environ.get("DATABASE_URL"), "Disposable PostgreSQL DATABASE_URL is required")
class PostgreSQLMemoryControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        memory.ensure_memory_schema()
        app = FastAPI(); app.include_router(memory_controls.router); app.add_middleware(memory_controls.MemoryBodyLimit)
        cls.client = TestClient(app)

    def setUp(self):
        self.subject = "test.memory-controls." + uuid.uuid4().hex
        self.ids = []

    def tearDown(self):
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM durable_memories WHERE subject_key = %s", (self.subject,))

    def create(self):
        response = self.client.post("/memories", json={"subject_key": self.subject, "category": "PROJECT",
                                                      "content": "The selected project uses PostgreSQL.", "confirmed": True})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["record"]

    def test_persist_correct_conflict_and_physical_delete(self):
        row = self.create()
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT content FROM durable_memories WHERE memory_id = %s", (uuid.UUID(row["id"]),))
                self.assertEqual(cur.fetchone()["content"], row["content"])
        self.assertEqual(self.client.post("/memories", json={"subject_key": self.subject, "content": "Different value",
                                                            "confirmed": True}).status_code, 409)
        correction = {"content": "Corrected project value", "expected_revision": row["revision"], "confirmed": True}
        response = self.client.patch("/memories/" + row["id"], json=correction)
        self.assertEqual(response.status_code, 200, response.text)
        changed = response.json()["record"]
        self.assertNotEqual(changed["revision"], row["revision"])
        self.assertEqual(self.client.patch("/memories/" + row["id"], json=correction).status_code, 409)
        self.assertEqual(self.client.post("/memories/" + row["id"] + "/delete",
                                         json={"expected_revision": row["revision"], "confirmed": True}).status_code, 409)
        listed = self.client.get("/memories").json()
        self.assertTrue(any(record["id"] == row["id"] and record["content"] == changed["content"] for record in listed["records"]))
        response = self.client.post("/memories/" + row["id"] + "/delete",
                                    json={"expected_revision": changed["revision"], "confirmed": True})
        self.assertEqual(response.status_code, 200)
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM durable_memories WHERE memory_id = %s", (uuid.UUID(row["id"]),))
                self.assertIsNone(cur.fetchone())

    def test_another_users_row_cannot_be_read_corrected_or_deleted(self):
        row = self.create()
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE durable_memories SET user_id = %s WHERE memory_id = %s", (uuid.uuid4(), uuid.UUID(row["id"])))
        self.assertFalse(any(record["id"] == row["id"] for record in self.client.get("/memories").json()["records"]))
        self.assertEqual(self.client.patch("/memories/" + row["id"], json={"content": "Overwrite attempt",
                                        "expected_revision": row["revision"], "confirmed": True}).status_code, 404)
        self.assertEqual(self.client.post("/memories/" + row["id"] + "/delete",
                         json={"expected_revision": row["revision"], "confirmed": True}).status_code, 404)

    def test_nonactive_records_require_explicit_deletion_not_reactivation(self):
        row = self.create()
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE durable_memories SET status = 'SUPERSEDED' WHERE memory_id = %s", (uuid.UUID(row["id"]),))
        record = next(record for record in self.client.get("/memories?status=SUPERSEDED").json()["records"] if record["id"] == row["id"])
        self.assertEqual(self.client.patch("/memories/" + row["id"], json={"content": "Reactivate attempt",
                         "expected_revision": record["revision"], "confirmed": True}).status_code, 409)

    def test_two_corrections_cannot_both_commit_the_same_review(self):
        row = self.create()
        def attempt(content):
            return self.client.patch("/memories/" + row["id"], json={"content": content,
                                      "expected_revision": row["revision"], "confirmed": True}).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(attempt, ["First correction", "Second correction"]))
        self.assertEqual(sorted(statuses), [200, 409])

    def test_pagination_is_bounded_and_records_do_not_disappear_at_page_boundary(self):
        ids = [uuid.uuid4() for _ in range(51)]
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.executemany("""INSERT INTO durable_memories
                                (memory_id, user_id, category, subject_key, content, normalized_content, confidence, status)
                                VALUES (%s, %s, 'PROJECT', %s, 'Fixture fact', 'fixture fact', 0.9, 'ACTIVE')""",
                                [(item, memory.DEFAULT_USER_ID, self.subject) for item in ids])
        first = self.client.get("/memories").json()
        second = self.client.get("/memories?page=1").json()
        self.assertEqual(len(first["records"]), 50)
        self.assertTrue(first["has_more"])
        observed = {item["id"] for item in first["records"] + second["records"]}
        self.assertTrue({str(item) for item in ids}.issubset(observed))


if __name__ == "__main__":
    unittest.main()
