"""Real PostgreSQL pause, resumption, concurrent stale reviews and ordering."""
import os
import sys
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/core'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import memory
import memory_controls

@unittest.skipUnless(os.environ.get('DATABASE_URL'), 'Disposable PostgreSQL is required')
class PostgreSQLPreferenceControls(unittest.TestCase):
    def setUp(self):
        memory.ensure_memory_schema()
        self.user = uuid.uuid4()
        self.scope = patch.object(memory, 'DEFAULT_USER_ID', self.user); self.scope.start()
        app = FastAPI(); app.include_router(memory_controls.router)
        self.client = TestClient(app)
        self.candidate = memory.DurableMemoryCandidate(memory.MemoryCategory.PREFERENCE, 'test.preference', 'I prefer brief answers.', 0.9, False)
    def tearDown(self):
        self.scope.stop()
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('DELETE FROM durable_memories WHERE user_id = %s', (self.user,))
                cur.execute('DELETE FROM memory_save_preferences WHERE user_id = %s', (self.user,))
    def save(self, enabled, revision):
        return self.client.patch('/memories/preferences', json=dict(automatic_saving=enabled, expected_revision=revision, confirmed=True))
    def test_persist_pause_manual_save_and_resume(self):
        initial = self.client.get('/memories/preferences').json()
        self.assertTrue(initial['automatic_saving']); self.assertFalse(initial['reviewed'])
        paused = self.save(False, initial['revision']); self.assertEqual(paused.status_code, 200, paused.text)
        self.assertIsNone(memory.promote_memory_candidate(self.candidate, None, self.user))
        manual = self.client.post('/memories', json=dict(subject_key='test.manual', content='Reviewed fact', confirmed=True))
        self.assertEqual(manual.status_code, 201, manual.text)
        self.assertEqual(len(self.client.get('/memories').json()['records']), 1)
        self.assertFalse(self.client.get('/memories/preferences').json()['automatic_saving'])
        self.assertEqual(self.save(True, '0').status_code, 409)
        resumed = self.save(True, paused.json()['revision']); self.assertEqual(resumed.status_code, 200)
        self.assertIsNotNone(memory.promote_memory_candidate(self.candidate, None, self.user))
        self.assertEqual(len(self.client.get('/memories').json()['records']), 2)
    def test_two_reviewed_changes_cannot_both_commit(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(lambda enabled: self.save(enabled, '0').status_code, [True, False]))
        self.assertEqual(sorted(statuses), [200, 409])
    def test_acknowledged_pause_waits_for_earlier_promotion(self):
        started = Event(); release = Event(); attempting = Event()
        def in_flight(*args):
            started.set()
            if not release.wait(10): raise RuntimeError('test timeout')
            return 'earlier promotion finished'
        def pause():
            attempting.set(); return self.save(False, '0')
        with patch.object(memory, '_promote_memory_candidate_unchecked', side_effect=in_flight):
            with ThreadPoolExecutor(max_workers=2) as pool:
                promotion = pool.submit(memory.promote_memory_candidate, self.candidate, None, self.user)
                self.assertTrue(started.wait(5))
                change = pool.submit(pause)
                try:
                    self.assertTrue(attempting.wait(5))
                    from concurrent.futures import TimeoutError
                    with self.assertRaises(TimeoutError): change.result(timeout=0.2)
                finally: release.set()
                self.assertEqual(promotion.result(timeout=5), 'earlier promotion finished')
                self.assertEqual(change.result(timeout=5).status_code, 200)
        self.assertIsNone(memory.promote_memory_candidate(self.candidate, None, self.user))

if __name__ == '__main__': unittest.main()
