"""Explicit per-thread cloud consent does not retrieve durable or foreign memory."""
import os,sys,unittest,uuid
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'));sys.path.insert(0,str(ROOT/'services/core'))
@unittest.skipUnless(os.environ.get('DATABASE_URL'),'Disposable PostgreSQL required')
class CloudContext(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main,memory
        cls.core=main;cls.memory=memory
    def test_consent_loads_only_current_owned_thread_and_preserves_order(self):
        core=self.core;memory=self.memory
        owner=memory.local_memory_user('cloud-test-'+uuid.uuid4().hex)
        foreign=memory.local_memory_user('cloud-test-'+uuid.uuid4().hex)
        thread=memory.create_conversation(user_id=owner)
        other=memory.create_conversation(user_id=foreign)
        try:
            memory.save_message(thread,'user','The project is Cedar.')
            memory.save_message(thread,'assistant','I will call it Cedar.')
            memory.save_message(other,'user','Foreign confidential information.')
            request=core.ChatRequest(message='What is its name?',allow_cloud_history=True)
            with patch.dict(os.environ,{'SHY_MODEL_BACKEND':'runpod'}),patch.object(core,'reply_generation_requires_local',return_value=False),patch.object(core,'_load_memory_history_for_message',side_effect=AssertionError('Must not retrieve saved memory')):
                history,local=core._load_request_history(request,thread,owner)
                self.assertFalse(local);self.assertEqual([x['role'] for x in history],['user','assistant'])
                self.assertIn('Cedar',history[0]['content'])
                self.assertEqual(core._load_request_history(request,other,owner),([],False))
                memory.save_message(thread,'user','x'*50000)
                history,_=core._load_request_history(request,thread,owner)
                self.assertLessEqual(sum(len(x['content']) for x in history),3200)
        finally:
            with memory.connect() as conn:
                with conn.cursor() as cur:
                    for user in [owner,foreign]:cur.execute('DELETE FROM users WHERE id=%s',(user,))
    def test_actual_chat_uses_consented_history_and_actual_cloud_runtime_facts(self):
        from fastapi.testclient import TestClient
        from types import SimpleNamespace
        core=self.core;memory=self.memory
        project='cloud-http-'+uuid.uuid4().hex
        owner=memory.local_memory_user(project)
        thread=memory.create_conversation(user_id=owner)
        try:
            memory.save_message(thread,'user','My sample project is Cedar.')
            memory.save_message(thread,'assistant','Your project is Cedar.')
            with patch.dict(os.environ,{'SHY_MODEL_BACKEND':'runpod','SHY_RUNPOD_ENDPOINT_ID':'fixture123','SHY_RUNPOD_API_KEY':'fixture-key'}),patch.object(core,'reply_generation_requires_local',return_value=False),patch.object(core,'reply_prompt_guidance',return_value=''):
                router=type(core.router)(core.LOCAL_MODEL,include_fake_providers=False)
                provider=router.registry.get_provider('runpod')
                with patch.object(core,'router',router),patch.object(core,'_load_memory_history_for_message',side_effect=AssertionError('Unexpected private retrieval')),patch.object(provider,'generate',return_value=SimpleNamespace(status='OK',content='Your project is Cedar.')) as generate:
                    response=TestClient(core.app).post('/chat',json={'message':"What is my sample project's name?",'project_id':project,'conversation_id':str(thread),'allow_cloud_history':True})
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(response.json()['provider'],'runpod')
                    request=generate.call_args.kwargs['request']
                    self.assertIn('RunPod cloud inference',request.messages[0].content)
                    self.assertTrue(any('Cedar' in m.content for m in request.messages[1:-1]))
                    self.assertEqual(request.metadata['privacy_requirement'],'REMOTE_ALLOWED')
                    generate.reset_mock()
                    response=TestClient(core.app).post('/chat',json={'message':'Say hello briefly.','project_id':project,'conversation_id':str(thread)})
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(response.json()['provider'],'runpod')
                    request=generate.call_args.kwargs['request']
                    self.assertFalse(any('Cedar' in m.content for m in request.messages))
                    self.assertEqual(request.metadata['privacy_requirement'],'REMOTE_ALLOWED')
        finally:
            with memory.connect() as conn:
                with conn.cursor() as cur:
                    cur.execute('DELETE FROM durable_memories WHERE user_id=%s',(owner,))
                    cur.execute('DELETE FROM users WHERE id=%s',(owner,))

    def test_default_omits_history_and_local_only_keeps_local_memory_policy(self):
        core=self.core
        with patch.dict(os.environ,{'SHY_MODEL_BACKEND':'runpod'}),patch.object(core,'reply_generation_requires_local',return_value=False),patch.object(core,'_load_memory_history_for_message',return_value=([{'role':'user','content':'local memory'}],True)) as loader:
            with patch.object(core,'load_messages',side_effect=AssertionError('Unconsented history read')):
                self.assertEqual(core._load_request_history(core.ChatRequest(message='Hello'),uuid.uuid4(),uuid.uuid4()),([],False))
            loader.assert_not_called()
            for request in [core.ChatRequest(message='Hello',allow_cloud_history=True,local_only=True)]:
                self.assertTrue(core._load_request_history(request,uuid.uuid4(),uuid.uuid4())[1])
            self.assertEqual(loader.call_count,1)
            with patch.object(core,'reply_generation_requires_local',return_value=True):
                self.assertTrue(core._load_request_history(core.ChatRequest(message='Hello',allow_cloud_history=True),uuid.uuid4(),uuid.uuid4())[1])
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):core.ChatRequest(message='Hello',allow_cloud_history='yes')
if __name__=='__main__':unittest.main()
