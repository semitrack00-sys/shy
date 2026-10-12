import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from research.freshness import source_timing, requested_window, window_selection, evidence_timing, validate_current_citations
from research.web_search import SearchResult, WebSearchService, WebSearchProvider
from research.tavily import TavilySearchProvider
from research.research_engine import ResearchEngine

NOW = datetime(2026, 10, 11, 12, tzinfo=timezone.utc)

class FreshnessTests(unittest.TestCase):
    def test_dates_bounds_timezone_and_future(self):
        for raw, status in [(None,'unknown'), ('','unknown'), ('2026-10-10','recent'),
            ('Sun, 11 Oct 2026 11:00:00 GMT','recent'), ('2026-10-11T12:00:00Z','recent'),
            ('2026-10-11T15:00:00+03:00','recent'), ('2026-10-12','future'),
            ('2026-10-11T12:01:00Z','future'), ('2026-09-01','stale'),
            ('2026-10-11T11:00:00','invalid'), ('bad','invalid'), ('2026-02-30','invalid'),
            ('x'*121,'invalid'), (123,'invalid')]:
            with self.subTest(raw=raw): self.assertEqual(source_timing(raw,NOW)['source_date_status'],status)
        self.assertEqual(source_timing('2026-10-10',NOW,0)['source_date_status'],'stale')
        self.assertEqual(source_timing('2026-10-04',NOW,7)['source_date_status'],'recent')
        self.assertEqual(source_timing('2026-10-03',NOW,7)['source_date_status'],'stale')
    def test_recency_hints_not_universal_language_detection(self):
        for query, expected in [('latest release',7),('today weather',0),('right now',0),
            ('this week',7),('recent developments',7),('history of Rome',None),('currently',None)]:
            self.assertEqual(requested_window(query),expected)
    def test_multilingual_normalization_minimum_and_boundaries(self):
        for query, expected in [
            ("AUJOURD’HUI", (0,'french_hint')),
            ("re\u0301centes nouvelles", (7,'french_hint')),
            ("en  ce\n moment", (0,'french_hint')),
            ("kounye a", (0,'haitian_creole_hint')),
            ("dènye enfòmasyon", (7,'haitian_creole_hint')),
            ("semèn sa a", (7,'haitian_creole_hint')),
            ("latest jodi a", (0,'haitian_creole_hint')),
            ("today aujourd'hui", (0,'mixed_hint')),
            ("jodias actuellement recently", (None,'no_window')),
            ("cette semaine latest", (7,'mixed_hint')),
        ]:
            with self.subTest(query=query):
                self.assertEqual(window_selection(query),expected)
                self.assertEqual(requested_window(query),expected[0])

    def test_retrieval_never_makes_unknown_date_recent_and_numbering_binds_to_url(self):
        payload={'results':[{'url':'https://example.com/b','source_date':'2026-01-01'},
                            {'url':'https://example.com/a','retrieved_at':NOW.isoformat()}]}
        sources=[{'number':1,'url':'https://example.com/a'}, {'number':2,'url':'https://example.com/b'}]
        reports=evidence_timing(payload,sources,NOW,7)
        self.assertEqual([x['source_date_status'] for x in reports],['unknown','stale'])
        for answer in ['Answer [1].','Answer [2].']:
            with self.assertRaises(ValueError):validate_current_citations(answer,sources,reports,7)
        validate_current_citations('Historical answer [2].',sources,reports,None)
    def test_mixed_dates_gate_and_duplicate_url_cannot_override_stale_row(self):
        sources=[{'number':1,'url':'https://example.com/a'}, {'number':2,'url':'https://example.com/b'}]
        payload={'results':[{'url':sources[0]['url'],'source_date':'2026-10-11'},
                            {'url':sources[1]['url'],'source_date':'2025-10-11'}]}
        reports=evidence_timing(payload,sources,NOW,7)
        validate_current_citations('Current [1].',sources,reports,7)
        with self.assertRaises(ValueError):validate_current_citations('Current [1] and old [2].',sources,reports,7)
        payload['results'].append({'url':sources[0]['url'],'source_date':'2020-01-01'})
        self.assertEqual(evidence_timing(payload,sources,NOW,7)[0]['source_date_status'],'stale')
    def test_tavily_requests_estimated_date_and_service_stamps_own_retrieval_time(self):
        fixture={'results':[{'url':'https://example.com/a','title':'A','content':'Evidence','published_date':'Sun, 11 Oct 2026 11:00:00 GMT'}]}
        response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:fixture)
        with patch('research.tavily.httpx.post',return_value=response) as post:
            output=WebSearchService(TavilySearchProvider(api_key='fixture-not-real')).search('Question')
        self.assertTrue(post.call_args.kwargs['json']['include_published_date'])
        row=output['results'][0]
        self.assertEqual(row['source_date'],fixture['results'][0]['published_date'])
        self.assertIsNotNone(datetime.fromisoformat(row['retrieved_at']).tzinfo)
        self.assertNotEqual(row['retrieved_at'],row['source_date'])
    def test_engine_keeps_date_and_retrieval_metadata(self):
        rows=[{'url':'https://example.com/a','title':'A',
               'source_date':'2026-10-11','retrieved_at':NOW.isoformat()}]
        engine=ResearchEngine(search_executor=lambda query, limit: {'results':rows})
        payload=engine.run('Public source question',max_queries=3,follow_up_budget=0).to_public_dict()
        self.assertEqual(payload['evidence'][0]['source_date'],'2026-10-11')
        self.assertEqual(payload['sources'][0]['retrieved_at'],NOW.isoformat())

if __name__=='__main__':unittest.main()
