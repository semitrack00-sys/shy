"""Real agent HTTP response guard with fixture search and generated text."""
import os
import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'services')); sys.path.insert(0, str(ROOT / 'services/core'))


@unittest.skipUnless(os.environ.get('DATABASE_URL'), 'Full runtime and disposable PostgreSQL required')
class ResearchGuardIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import main
        from fastapi.testclient import TestClient
        cls.core = main; cls.client = TestClient(main.app)
    def call_agent(self, answer, url='https://example.com/source'):
        search = SimpleNamespace(status='TOOL_RESULT',tool_name='web.search',tool_status='EXECUTED',reason='fixture',
                                 output={'provider':'fixture','results':[{'url':url,'title':'Source','snippet':'Supplied evidence.','source':'example.com'}]})
        with patch.object(self.core.agent_runtime, 'run', return_value=search), patch.object(self.core, 'generate_intelligence_response', AsyncMock(return_value=answer)) as generation:
            response = self.client.post('/agent', json={'message':'Search public source evidence'})
            return response, generation
    def test_valid_numeric_citation_returns_existing_source(self):
        response, generation = self.call_agent('Supplied evidence [1].')
        self.assertEqual(response.status_code, 200, response.text); self.assertEqual(response.json()['status'], 'RESPOND')
        self.assertEqual(response.json()['sources'][0]['number'], 1)
        self.assertEqual(response.json()['message'], 'Supplied evidence [1].')
        self.assertIn('UNTRUSTED EXTERNAL EVIDENCE', generation.call_args.kwargs['message'])
    def test_invented_uncited_malformed_and_external_urls_never_return_model_answer(self):
        for answer in ['Unsupported answer.', 'Invented reference [44].', 'Wrong [bad].',
                       'Evidence [1] with invented URL https://madeup.example/x']:
            response, generation = self.call_agent(answer)
            self.assertEqual(response.status_code, 200, response.text)
            payload = response.json(); self.assertEqual(payload['status'], 'FAILED')
            self.assertNotIn('message', payload); self.assertNotIn(answer, response.text)
            self.assertEqual(generation.await_count, 1)
    def test_prompt_numbers_match_displayed_source_table_when_order_differs(self):
        payload = {'evidence':[{'title':'B','url':'https://example.com/b','snippet':'B evidence'},
                               {'title':'A','url':'https://example.com/a','snippet':'A evidence'}],
                   'sources':[{'number':1,'url':'https://example.com/a'}, {'number':2,'url':'https://example.com/b'}]}
        with patch.object(self.core, 'generate_intelligence_response', AsyncMock(return_value='B evidence [2].')) as generation:
            answer = asyncio.run(self.core.generate_research_response('Question', research_result=payload))
            prompt = generation.call_args.kwargs['message']
            self.assertIn('[2] TITLE: B', prompt); self.assertIn('[1] TITLE: A', prompt)
            self.assertEqual(answer, 'B evidence [2].')
    def test_unsafe_source_fails_before_model_generation(self):
        response, generation = self.call_agent('Evidence [1].', 'javascript:alert(1)')
        self.assertEqual(response.json()['status'], 'FAILED'); self.assertEqual(generation.await_count, 0)


if __name__ == '__main__': unittest.main()
