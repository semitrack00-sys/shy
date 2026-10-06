"""Preference validation and fail-closed automatic promotion."""
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/core'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import memory
import memory_controls

class PreferenceContracts(unittest.TestCase):
    def setUp(self):
        app = FastAPI(); app.include_router(memory_controls.router)
        app.add_middleware(memory_controls.MemoryBodyLimit)
        self.client = TestClient(app)

    def test_strict_confirmation_and_no_client_user_scope(self):
        for fields in [dict(confirmed=1), dict(confirmed=False), dict(automatic_saving='false'),
                       dict(user_id=str(uuid.uuid4())), dict(expected_revision='-1')]:
            body = dict(automatic_saving=False, expected_revision='0', confirmed=True); body.update(fields)
            self.assertEqual(self.client.patch('/memories/preferences', json=body).status_code, 422)

    def test_unavailable_database_rejects_setting_without_leaking_details(self):
        with patch.object(memory, 'connect', side_effect=RuntimeError('private database credential')):
            for response in [self.client.get('/memories/preferences'), self.client.patch('/memories/preferences',
                    json=dict(automatic_saving=False, expected_revision='0', confirmed=True))]:
                self.assertEqual(response.status_code, 503)
                self.assertNotIn('credential', response.text)

    def test_paused_or_unreadable_preference_cannot_promote(self):
        conn = MagicMock(); cur = conn.__enter__.return_value.cursor.return_value.__enter__.return_value
        with patch.object(memory, 'connect', return_value=conn), patch.object(memory, 'read_memory_save_preference',
                return_value={'automatic_saving': False}), patch.object(memory, '_promote_memory_candidate_unchecked') as promote:
            self.assertIsNone(memory.promote_memory_candidate(None, None))
            promote.assert_not_called()
            cur.execute.assert_called_once()
        with patch.object(memory, 'connect', side_effect=RuntimeError('unavailable')), patch.object(memory, '_promote_memory_candidate_unchecked') as promote:
            with self.assertRaises(RuntimeError): memory.promote_memory_candidate(None, None)
            promote.assert_not_called()

if __name__ == '__main__': unittest.main()
