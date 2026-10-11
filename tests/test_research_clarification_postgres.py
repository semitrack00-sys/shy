"""Actual research agent/chat paths, no generation for deterministic clarification."""
import os
import sys
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services'));sys.path.insert(0,str(ROOT/'services/core'))
NOW=datetime(2026,10,11,12,tzinfo=timezone.utc)

@unittest.skipUnless(os.environ.get('DATABASE_URL'),'Disposable PostgreSQL required')
class ClarificationIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        import memory
        from fastapi.testclient import TestClient
        cls.core=main;cls.memory=memory;memory.ensure_memory_schema();cls.client=TestClient(main.app)
    def setUp(self):self.project='research-'+uuid.uuid4().hex
    def tearDown(self):
        with self.memory.connect() as conn:
            with conn.cursor() as cur:
                owner=self.memory.local_memory_user(self.project)
                cur.execute('DELETE FROM durable_memories WHERE user_id=%s',(owner,))
                cur.execute('DELETE FROM users WHERE id=%s',(owner,))
    def search(self, snippets, dates=None):
        return {'provider':'fixture','results':[{'url':f'https://example.com/source-{i}',
            'title':f'Source {i}','source':'example.com','snippet':text,
            **({'source_date':dates[i]} if dates else {})} for i,text in enumerate(snippets)]}
    def agent(self, data, message='Search Acme launch date information'):
        result=SimpleNamespace(status='TOOL_RESULT',tool_name='web.search',tool_status='EXECUTED',reason='fixture',output=data)
        with patch.object(self.core.agent_runtime,'run',return_value=result), patch.object(self.core,'utc_now',return_value=NOW), patch.object(self.core,'generate_intelligence_response',AsyncMock(side_effect=AssertionError('Must not generate'))) as generation:
            response=self.client.post('/agent',json={'message':message})
        self.assertEqual(response.status_code,200,response.text);self.assertEqual(generation.await_count,0)
        return response.json()
    def test_actual_agent_disagreement_and_empty_excerpt_provenance(self):
        data=self.search(['Acme launch date: 2026-10-12','Acme launch date: 2026-11-01'])
        answer=self.agent(data)
        self.assertEqual(answer['research_answer']['mode'],'possible_disagreement')
        self.assertFalse(answer['research_answer']['model_invoked'])
        self.assertIn('2026-10-12 [1]',answer['message']);self.assertIn('2026-11-01 [2]',answer['message'])
        empty=self.agent(self.search(['','  ']))
        self.assertEqual(empty['research_answer']['mode'],'missing_excerpts')
    def test_recent_empty_excerpt_cannot_use_stale_body(self):
        data=self.search(['','Supplied old evidence'],['2026-10-11','2020-01-01'])
        answer=self.agent(data,'Search latest Acme information')
        self.assertEqual(answer['research_answer']['mode'],'missing_excerpts')
    def test_actual_chat_persists_clarification_and_returns_source_cards(self):
        data=self.search(['Acme launch date: 2026-10-12','Acme launch date: 2026-11-01'])
        service=SimpleNamespace(search=lambda query,max_results:data)
        with patch.object(self.core,'research_service',service), patch.object(self.core,'generate_intelligence_response',AsyncMock(side_effect=AssertionError('Must not generate'))) as generation:
            response=self.client.post('/chat',json={'message':'Research Acme launch date information','project_id':self.project})
        self.assertEqual(response.status_code,200,response.text);answer=response.json()
        self.assertEqual(answer['status'],'RESPOND');self.assertEqual(answer['execution_mode'],'RESEARCH')
        self.assertEqual(generation.await_count,0)
        self.assertEqual(answer['model'],'research-evidence-checks');self.assertEqual(answer['provider'],'shy-core')
        self.assertFalse(answer['cognitive']['model_invoked']);self.assertEqual(answer['cognitive']['model_roles_used'],[])
        self.assertEqual(answer['cognitive']['verification_status'],'INSUFFICIENT_EVIDENCE')
        self.assertIsNone(answer['model_routing'])
        self.assertEqual(len(answer['sources']),2)
        history=self.memory.load_messages(uuid.UUID(answer['conversation_id']),user_id=self.memory.local_memory_user(self.project))
        self.assertEqual([row['role'] for row in history],['user','assistant'])
        self.assertEqual(history[-1]['content'],answer['message'])
    def test_actual_chat_missing_recent_evidence_does_not_report_model_invocation(self):
        service=SimpleNamespace(search=lambda query,max_results:self.search(['Supplied undated evidence']))
        with patch.object(self.core,'research_service',service), patch.object(self.core,'generate_intelligence_response',AsyncMock(side_effect=AssertionError('Must not generate'))):
            response=self.client.post('/chat',json={'message':'Research latest Acme information','project_id':self.project})
        self.assertEqual(response.status_code,200,response.text);answer=response.json()
        self.assertEqual(answer['research_answer']['mode'],'missing_recent_evidence')
        self.assertFalse(answer['cognitive']['model_invoked'])
        self.assertEqual(answer['model'],'research-evidence-checks')

if __name__=='__main__':unittest.main()
