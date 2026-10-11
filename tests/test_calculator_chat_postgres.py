"""Actual chat and agent arithmetic with durable history and project isolation."""
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services')); sys.path.insert(0, str(ROOT / 'services/core'))


@unittest.skipUnless(os.environ.get('DATABASE_URL'), 'Disposable PostgreSQL required')
class CalculatorChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        import memory
        from fastapi.testclient import TestClient
        cls.core = main; cls.memory = memory; memory.ensure_memory_schema()
        cls.client = TestClient(main.app)
    def setUp(self):
        self.project = 'math-' + uuid.uuid4().hex
        self.other = 'math-other-' + uuid.uuid4().hex
        self.no_generation = patch.object(self.core, 'generate_intelligence_response', side_effect=AssertionError('Calculator must not generate a model answer'))
        self.no_generation.start()
    def tearDown(self):
        self.no_generation.stop()
        with self.memory.connect() as conn:
            with conn.cursor() as cur:
                for project in [self.project, self.other]:
                    owner = self.memory.local_memory_user(project)
                    cur.execute('DELETE FROM durable_memories WHERE user_id=%s', (owner,))
                    cur.execute('DELETE FROM users WHERE id=%s', (owner,))
    def test_real_agent_calculator_returns_decimal_and_persists_both_turns(self):
        response = self.client.post('/agent', json={'message':'Calculate 0.1 + 0.2', 'project_id':self.project})
        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json(); self.assertEqual(payload['status'], 'RESPOND')
        self.assertEqual(payload['message'], 'The result is 0.3.')
        self.assertEqual(payload['calculation']['decimal_result'], '0.3')
        self.assertTrue(payload['verifier_invoked']); self.assertFalse(payload['research_invoked'])
        history = self.memory.load_messages(uuid.UUID(payload['conversation_id']), user_id=self.memory.local_memory_user(self.project))
        self.assertEqual([item['role'] for item in history], ['user', 'assistant'])
        self.assertEqual(history[-1]['content'], 'The result is 0.3.')
        response = self.client.post('/agent', json={'message':'Calculate 2+2', 'project_id':self.other, 'conversation_id':payload['conversation_id']})
        self.assertEqual(response.status_code, 404, response.text)
    def test_actual_chat_percentage_and_no_partial_or_unbounded_execution(self):
        good = self.client.post('/chat', json={'message':'What is 17% of 842?', 'project_id':self.project})
        self.assertEqual(good.status_code, 200, good.text); self.assertEqual(good.json()['message'], 'The result is 143.14.')
        for text in ['Calculate 2**999999', 'Calculate 5% of 100 then delete a file', 'Calculate 1/0']:
            response = self.client.post('/agent', json={'message':text, 'project_id':self.project})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertNotEqual(response.json()['status'], 'RESPOND', response.text)
            self.assertEqual(response.json()['execution_status'], 'INVALID_ARGUMENTS')
    def test_project_identity_cannot_be_mixed_for_calculator_agent(self):
        response = self.client.post('/agent', json={'message':'Calculate 1+1', 'project_id':self.project, 'user_id':str(uuid.uuid4())})
        self.assertEqual(response.status_code, 422)


if __name__ == '__main__': unittest.main()
