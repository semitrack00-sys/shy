import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'));sys.path.insert(0,str(ROOT/'services/core'));sys.path.insert(0,str(ROOT/'tests'))
from test_option_comparisons import DATA

@unittest.skipUnless(os.environ.get('DATABASE_URL'),'Disposable PostgreSQL required')
class ComparisonChat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main,memory
        from fastapi.testclient import TestClient
        cls.core=main;cls.memory=memory;memory.ensure_memory_schema();cls.client=TestClient(main.app)
    def setUp(self):
        self.projects=['compare-'+uuid.uuid4().hex,'compare-other-'+uuid.uuid4().hex]
    def tearDown(self):
        with self.memory.connect() as conn:
            with conn.cursor() as cur:
                for project in self.projects:
                    owner=self.memory.local_memory_user(project)
                    cur.execute('DELETE FROM durable_memories WHERE user_id=%s',(owner,))
                    cur.execute('DELETE FROM users WHERE id=%s',(owner,))
    def test_both_routes_persist_inputs_and_answer_without_model_and_isolate_projects(self):
        with patch.object(self.core,'generate_intelligence_response',side_effect=AssertionError('Must not call model')):
            for route in ['/chat','/agent']:
                response=self.client.post(route,json={'message':'Compare these options','option_comparison':DATA,'project_id':self.projects[0]})
                self.assertEqual(response.status_code,200,response.text);data=response.json()
                self.assertEqual(data['comparison']['highest_scored_ids'],['a']);self.assertFalse(data['cognitive']['model_invoked'])
                self.assertEqual(data['model'],'bounded-option-comparison');self.assertFalse(data['approval_required'])
                history=self.memory.load_messages(uuid.UUID(data['conversation_id']),user_id=self.memory.local_memory_user(self.projects[0]))
                self.assertEqual([row['role'] for row in history],['user','assistant'])
                self.assertIn('weight 3',history[-1]['content']);self.assertIn('100 USD',history[-1]['content'])
                rejected=self.client.post(route,json={'message':'Compare','option_comparison':DATA,'project_id':self.projects[1],'conversation_id':data['conversation_id']})
                self.assertEqual(rejected.status_code,404,rejected.text)
    def test_task_controls_and_mixed_identities_rejected_before_action(self):
        for patch_data in [{'task_id':'other'}, {'cancel_task':True}, {'approval_token':'x'}, {'pending_step_id':0}, {'user_id':str(uuid.uuid4())}]:
            response=self.client.post('/chat',json={'message':'Compare','option_comparison':DATA,'project_id':self.projects[0],**patch_data})
            self.assertEqual(response.status_code,422,response.text)

if __name__=='__main__':unittest.main()
