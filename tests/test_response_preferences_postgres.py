import os,sys,unittest,uuid
from pathlib import Path
from unittest.mock import patch,AsyncMock
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'));sys.path.insert(0,str(ROOT/'services/core'))
@unittest.skipUnless(os.environ.get('DATABASE_URL'),'Disposable PostgreSQL required')
class PreferencePersistence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main,memory,response_preferences
        from fastapi.testclient import TestClient
        cls.core=main;cls.memory=memory;cls.prefs=response_preferences;memory.ensure_memory_schema();cls.client=TestClient(main.app)
    def setUp(self):self.projects=['reply-'+uuid.uuid4().hex,'reply-other-'+uuid.uuid4().hex]
    def tearDown(self):
        with self.memory.connect() as conn:
            with conn.cursor() as cur:
                for project in self.projects:
                    owner=self.memory.local_memory_user(project)
                    for table in ['response_preferences','durable_memories']:
                        cur.execute('DELETE FROM '+table+' WHERE user_id=%s',(owner,))
                    cur.execute('DELETE FROM users WHERE id=%s',(owner,))
    def read(self,project=None):return self.client.get('/memories/response-preferences',params={'project_id':project or self.projects[0]})
    def save(self,revision='0',enabled=True,language='ht'):
        return self.client.patch('/memories/response-preferences',params={'project_id':self.projects[0]},json={'enabled':enabled,'language':language,'detail':'short','tone':'plain','expected_revision':revision,'confirmed':True})
    def test_actual_persistence_consent_stale_revision_disable_and_project_isolation(self):
        first=self.read().json();self.assertFalse(first['enabled']);self.assertFalse(first['reviewed']);self.assertEqual(first['revision'],'0')
        saved=self.save();self.assertEqual(saved.status_code,200,saved.text);self.assertEqual(self.read().json()['language'],'ht')
        self.assertEqual(self.save().status_code,409);self.assertFalse(self.read(self.projects[1]).json()['enabled'])
        disabled=self.save('1',False);self.assertEqual(disabled.status_code,200,disabled.text);self.assertEqual(disabled.json()['revision'],'2');self.assertFalse(self.read().json()['enabled'])
        self.assertEqual(self.save('1').status_code,409)
        enabled=self.save('2',True,'fr');self.assertEqual(enabled.json()['revision'],'3')
        self.assertEqual(self.save('0').status_code,409)
    def test_concurrent_reviews_only_one_wins(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(lambda _:self.save().status_code,range(2)))
        self.assertEqual(sorted(statuses),[200,409]);self.assertEqual(self.read().json()['revision'],'1')
    def test_enabled_defaults_never_reach_a_hosted_candidate_even_with_bad_routing_labels(self):
        self.assertEqual(self.save().status_code,200)
        route=SimpleNamespace(selected_provider='hosted',selected_model='hosted-model',provider_health='HEALTHY',latency_tier='FAST',cost_tier='LOW',fallback_candidates=[],reason_code='COMPLEXITY')
        base_route=self.core.router.route('Describe how a library catalogue works.',privacy_requirement=self.core.PrivacyClass.LOCAL_ONLY)
        with patch.object(self.core.router,'route',return_value=base_route),patch.object(self.core.router,'build_routing_decision',return_value=route),patch.object(self.core,'_execute_ollama_candidate',new_callable=AsyncMock,side_effect=AssertionError('No local candidate in bad routing fixture')),patch.object(self.core.router.registry,'get_provider',side_effect=AssertionError('Hosted provider must not receive preferences')):
            response=self.client.post('/chat',json={'message':'Describe how a library catalogue works.','project_id':self.projects[0]})
        self.assertEqual(response.status_code,503,response.text)
        self.assertIsNone(self.prefs.current_preferences.get())

    def test_actual_generation_prompt_is_scoped_and_deterministic_replies_stay_exact(self):
        self.assertEqual(self.save().status_code,200)
        with patch.object(self.core.router,'build_routing_decision',return_value=None),patch.object(self.core,'_execute_ollama_candidate',new_callable=AsyncMock,return_value='Fixture prose.') as generation,patch.object(self.core,'_run_cognitive_deterministic_response',return_value=None),patch.object(self.core,'_try_ingest_request_knowledge',return_value=None):
            for route in ['/chat','/agent']:
                response=self.client.post(route,json={'message':'Describe how a library catalogue works.','project_id':self.projects[0]})
                self.assertEqual(response.status_code,200,response.text);data=response.json()
                self.assertIn('Haitian Creole',generation.call_args.args[0][0]['content'])
                self.assertTrue(data['response_preferences']['applied_to_model_prompt']);self.assertFalse(data['response_preferences']['output_style_verified'])
                other=self.client.post(route,json={'message':'Describe how a library catalogue works.','project_id':self.projects[1]})
                self.assertEqual(other.status_code,200,other.text);self.assertNotIn('Reviewed reply defaults',generation.call_args.args[0][0]['content'])
                self.assertFalse(other.json()['response_preferences']['applied_to_model_prompt'])
        response=self.client.post('/chat',json={'message':'Calculate 0.1+0.2','project_id':self.projects[0]})
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(response.json()['message'],'The result is 0.3.');self.assertFalse(response.json()['response_preferences']['applied_to_model_prompt'])
        self.assertIsNone(self.prefs.current_preferences.get())
if __name__=='__main__':unittest.main()
