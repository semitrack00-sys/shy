"""Exercise the real chat handler, project ownership and memory preferences."""
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services')); sys.path.insert(0, str(ROOT / 'services/core'))

@unittest.skipUnless(os.environ.get('DATABASE_URL'), 'Full runtime and disposable PostgreSQL are required')
class ProjectMemoryIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        import memory
        from fastapi.testclient import TestClient
        cls.core = main; cls.memory = memory
        memory.ensure_memory_schema()
        cls.client = TestClient(main.app)
    def setUp(self):
        self.projects = ['test-a-' + uuid.uuid4().hex, 'test-b-' + uuid.uuid4().hex]
        self.ids = []
        # Deterministic response only replaces generation, not memory loading/saving.
        self.response = patch.object(self.core, '_run_basic_system_response', return_value=('Fixture reply.', {}, 'fixture'))
        self.response.start()
        self.knowledge = patch.object(self.core, '_try_ingest_request_knowledge', return_value=None); self.knowledge.start()
    def tearDown(self):
        self.knowledge.stop(); self.response.stop()
        with self.memory.connect() as conn:
            with conn.cursor() as cur:
                for project in self.projects:
                    user = self.memory.local_memory_user(project)
                    cur.execute('DELETE FROM durable_memories WHERE user_id = %s', (user,))
                    cur.execute('DELETE FROM memory_save_preferences WHERE user_id = %s', (user,))
                    cur.execute('DELETE FROM users WHERE id = %s', (user,))
                for conversation in self.ids:
                    cur.execute('DELETE FROM conversations WHERE id = %s', (uuid.UUID(conversation),))
    def chat(self, project, message, conversation=None):
        body = {'message': message}
        if project: body['project_id'] = project
        if conversation: body['conversation_id'] = conversation
        response = self.client.post('/chat', json=body)
        if response.status_code == 200 and response.json().get('conversation_id'):
            self.ids.append(response.json()['conversation_id'])
        return response
    def test_ordinary_chat_obeys_the_default_users_pause(self):
        preference = self.client.get('/memories/preferences').json()
        paused = self.client.patch('/memories/preferences', json=dict(automatic_saving=False,
            expected_revision=preference['revision'], confirmed=True))
        self.assertEqual(paused.status_code, 200, paused.text)
        before = self.client.get('/memories').json()['records']
        try:
            response = self.chat(None, 'My company is Test Default Scope Company.')
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['status'], 'RESPOND')
            self.assertEqual(self.core._effective_user_uuid_from_request(self.core.ChatRequest(message='Hello')),
                             self.memory.DEFAULT_USER_ID)
            self.assertEqual([(row['id'],row['content'],row['status']) for row in self.client.get('/memories').json()['records']],
                             [(row['id'],row['content'],row['status']) for row in before])
        finally:
            with self.memory.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute('DELETE FROM memory_save_preferences WHERE user_id = %s', (self.memory.DEFAULT_USER_ID,))
                    if preference['reviewed']:
                        cur.execute('INSERT INTO memory_save_preferences (user_id, automatic_saving, revision) VALUES (%s,%s,%s)',
                                    (self.memory.DEFAULT_USER_ID, preference['automatic_saving'], int(preference['revision'])))
    def test_project_chat_durable_history_and_manual_changes_are_isolated(self):
        a, b = self.projects
        first = self.chat(a, 'I prefer dark mode.'); second = self.chat(b, 'I prefer light mode.')
        self.assertEqual(first.status_code, 200, first.text); self.assertEqual(second.status_code, 200, second.text)
        ca = first.json()['conversation_id']; cb = second.json()['conversation_id']
        self.assertEqual(self.chat(b, 'Recall my preferences', ca).status_code, 404)
        ma = self.client.get('/memories', params={'project_id': a}).json()['records']
        mb = self.client.get('/memories', params={'project_id': b}).json()['records']
        self.assertTrue(any('dark' in row['content'].lower() for row in ma), ma)
        self.assertTrue(any('light' in row['content'].lower() for row in mb), mb)
        self.assertFalse(any('light' in row['content'].lower() for row in ma))
        row = ma[0]
        self.assertEqual(self.client.patch('/memories/' + row['id'], params={'project_id': b},
            json=dict(content='Cross-project overwrite', expected_revision=row['revision'], confirmed=True)).status_code, 404)
        self.assertEqual(self.client.post('/memories/' + row['id'] + '/delete', params={'project_id': b},
            json=dict(expected_revision=row['revision'], confirmed=True)).status_code, 404)
        usera = self.memory.local_memory_user(a)
        self.assertEqual(self.memory.load_messages(uuid.UUID(cb), user_id=usera), [])
        query = self.memory.build_memory_query('preference mode', uuid.UUID(ca), usera, include_cross_conversation=True)
        records = self.memory.load_memory_records(query)
        self.assertTrue(records); self.assertTrue(all(item.user_id == usera for item in records))
        durable = self.memory.retrieve_durable_memory_context('preferred display mode', uuid.UUID(ca), usera)
        self.assertTrue(durable.selected_records)
        self.assertTrue(all(item.user_id == usera for item in durable.selected_records))
    def test_project_preferences_do_not_pause_another_project(self):
        a,b = self.projects
        self.assertEqual(self.client.patch('/memories/preferences', params={'project_id': a},
            json=dict(automatic_saving=False, expected_revision='0', confirmed=True)).status_code, 200)
        self.assertEqual(self.chat(a, 'I prefer dark mode.').status_code, 200)
        self.assertEqual(self.chat(b, 'I prefer light mode.').status_code, 200)
        self.assertEqual(self.client.get('/memories', params={'project_id': a}).json()['records'], [])
        self.assertTrue(self.client.get('/memories', params={'project_id': b}).json()['records'])
    def test_invalid_and_mixed_scopes_are_rejected(self):
        for project in ['../escape', '', 'A', 'x' * 65]:
            self.assertEqual(self.client.get('/memories', params={'project_id': project}).status_code, 422)
            self.assertEqual(self.client.post('/chat', json={'message':'Hello', 'project_id':project}).status_code, 422)
        self.assertEqual(self.client.post('/chat', json={'message':'Hello', 'project_id':self.projects[0],
                         'user_id':str(uuid.uuid4())}).status_code, 422)
    def test_legacy_anonymous_default_memory_is_migrated_to_local_controls(self):
        item = uuid.uuid4(); legacy = uuid.uuid5(uuid.NAMESPACE_DNS, 'default||anonymous')
        with self.memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""INSERT INTO durable_memories (memory_id,user_id,category,subject_key,content,normalized_content,confidence)
                    VALUES (%s,%s,'USER_FACT','test.legacy.default','Legacy fact','legacy fact',0.9)""", (item, legacy))
        try:
            self.memory.ensure_memory_schema()
            with self.memory.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT user_id FROM durable_memories WHERE memory_id = %s', (item,))
                    self.assertEqual(cur.fetchone()['user_id'], self.memory.DEFAULT_USER_ID)
        finally:
            with self.memory.connect() as conn:
                with conn.cursor() as cur: cur.execute('DELETE FROM durable_memories WHERE memory_id = %s', (item,))

if __name__ == '__main__': unittest.main()
