"""Document parser, provenance, validation and request resource bounds."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'services/core'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import documents

class DocumentContracts(unittest.TestCase):
    def setUp(self):
        app=FastAPI(); app.include_router(documents.router); app.add_middleware(documents.DocumentBodyLimit)
        self.client=TestClient(app)
    def test_chunks_preserve_original_text_and_unicode_provenance(self):
        text='Préférences: kreyòl ayisyen.\n' + ('Long source line ' * 500) + '\nFinal source line.'
        chunks, info=documents.prepare(text,'text')
        self.assertEqual(''.join(chunk[2] for chunk in chunks),text)
        self.assertTrue(all(len(chunk[2]) <= 1000 for chunk in chunks))
        self.assertEqual(chunks[0][0],1); self.assertEqual(chunks[-1][1],3)
        self.assertFalse(info['formula_like_cells'])
    def test_csv_limits_and_formula_values_are_never_executed(self):
        chunks, info=documents.prepare('name,value\n"Quoted, name",=1+2\nHaiti,+509\n','csv')
        self.assertEqual(info['formula_like_cells'],2); self.assertEqual(info['rows'],3)
        self.assertIn('=1+2',''.join(item[2] for item in chunks))
        for text in ['"unclosed', 'x,'*51, 'x\n'*1001, 'x'*4001]:
            with self.assertRaises(Exception): documents.prepare(text,'csv')
    def test_strict_review_names_content_and_selection_bounds(self):
        base=dict(name='notes.txt',kind='text',content='Source note',confirmed=True)
        for fields in [dict(confirmed=1),dict(confirmed=False),dict(name='../notes.txt'),dict(content='\0'),
                       dict(content='é'*140000),dict(user_id='other'),dict(kind='pdf')]:
            payload={**base,**fields}
            self.assertEqual(self.client.post('/documents',json=payload).status_code,422)
        for payload in [dict(query='notes',document_ids=[]),dict(query='notes',document_ids=['invalid']),
                        dict(query='notes',document_ids=['00000000-0000-0000-0000-000000000001']*2)]:
            self.assertEqual(self.client.post('/documents/search',json=payload).status_code,422)
    def test_streamed_body_limit_nonfinite_json_and_generic_database_errors(self):
        self.assertEqual(self.client.post('/documents',content=b'x'*(documents.MAX_REQUEST_BYTES+1)).status_code,413)
        self.assertEqual(self.client.post('/documents',content=b'{"content":NaN}').status_code,422)
        with patch.object(documents.memory,'connect',side_effect=RuntimeError('private credential')):
            response=self.client.get('/documents'); self.assertEqual(response.status_code,503)
            self.assertNotIn('credential',response.text)

if __name__=='__main__': unittest.main()
