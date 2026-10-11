import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services'))
from research.synthesis_guard import public_source_url, synthesis_sources, validate_synthesis


class SynthesisGuard(unittest.TestCase):
    def test_citation_membership_and_no_invented_urls(self):
        sources = synthesis_sources({'results':[{'url':'https://example.com/one'}, {'url':'https://example.org/two'}]})
        validate_synthesis('Source one says this [1]; source two differs [2].', sources)
        validate_synthesis('See https://example.com/one [1].', sources)
        for answer in ['Uncited answer.', 'Wrong source [9].', 'Malformed [abc].',
                       'Good [1] but invented https://invented.example/x', 'Good [1] and wrong [99].',
                       'Good [1]' + '[1]'*101, 'x'*20001+' [1]']:
            with self.subTest(answer=answer[:60]):
                with self.assertRaises(ValueError): validate_synthesis(answer, sources)
    def test_bad_provenance_and_evidence_bounds_fail_before_generation(self):
        for payload in [{}, {'evidence':'bad'}, {'evidence':[None]}, {'evidence':[{'url':'javascript:alert(1)'}]},
                        {'results':[{'url':'https://example.com'}]*13}]:
            with self.assertRaises(ValueError): synthesis_sources(payload)
    def test_supplied_source_numbers_bind_to_the_same_evidence_urls(self):
        evidence = [{'url':'https://example.com/b'}, {'url':'https://example.com/a'}]
        source_table = [{'number':1,'url':'https://example.com/a'}, {'number':2,'url':'https://example.com/b'}]
        self.assertEqual(synthesis_sources({'evidence':evidence, 'sources':source_table}), source_table)
        for sources in [[{'number':1,'url':'https://invented.example/source'}, source_table[1]],
                        [{'number':1,'url':'https://example.com/a'}]*2,
                        [{'number':2,'url':'https://example.com/a'}, {'number':4,'url':'https://example.com/b'}]]:
            with self.assertRaises(ValueError): synthesis_sources({'evidence':evidence,'sources':sources})
    def test_public_url_syntax_does_not_resolve_or_fetch(self):
        for url in ['https://example.com/source', 'http://www.example.org/page', 'https://8.8.8.8/source']:
            self.assertTrue(public_source_url(url), url)
        for url in ['javascript:alert(1)', 'file:///etc/passwd', 'https://localhost/x', 'https://private.local/x',
                    'https://127.0.0.1/x', 'http://[::1]/x', 'https://10.0.0.1/x', 'https://user:pass@example.com',
                    'https://example.com:9000/x', 'https://example.com\n/x', 'https://example.com\\evil',
                    'https://2130706433/x', 'https://999.999.999.999/x', 'http://0x7f.0.0.1/x']:
            self.assertFalse(public_source_url(url), url)
    def test_membership_is_not_claim_truth_verification(self):
        sources = synthesis_sources({'results':[{'url':'https://example.com/source'}]})
        # This check intentionally makes no semantic correctness claim.
        validate_synthesis('A supplied claim has citation [1].', sources)


if __name__ == '__main__': unittest.main()
