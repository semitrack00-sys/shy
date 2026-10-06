"""Real local document persistence, full-text indexing, revisions and isolation."""
import os
import sys
import unittest
import uuid
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/core'))
from fastapi import FastAPI
from fastapi.testclient import TestClient
import documents
import memory

@unittest.skipUnless(os.environ.get('DATABASE_URL'),'Disposable PostgreSQL is required')
class PostgreSQLDocuments(unittest.TestCase):
    def setUp(self):
        documents.ensure_document_schema()
        self.projects=['docs-a-'+uuid.uuid4().hex,'docs-b-'+uuid.uuid4().hex]
        app=FastAPI();app.include_router(documents.router);app.add_middleware(documents.DocumentBodyLimit)
        self.client=TestClient(app)
    def tearDown(self):
        with memory.connect() as conn:
            with conn.cursor() as cur:
                for project in self.projects:
                    cur.execute('DELETE FROM local_documents WHERE user_id=%s',(memory.local_memory_user(project),))
    def upload(self, content, project=None, name='notes.txt', kind='text'):
        response=self.client.post('/documents',params={'project_id':project or self.projects[0]},
            json=dict(name=name,kind=kind,content=content,confirmed=True))
        self.assertEqual(response.status_code,201,response.text);return response.json()['document']
    def search(self, ids, query, project=None, endpoint='search'):
        return self.client.post('/documents/'+endpoint,params={'project_id':project or self.projects[0]},
            json=dict(document_ids=ids,query=query,limit=5))
    def test_persistence_search_exact_provenance_and_scope(self):
        text='Project uses PostgreSQL.\nPréférences: français et kreyòl ayisyen.\nCost: 42 dollars.'
        row=self.upload(text)
        self.assertEqual(self.client.get('/documents/'+row['id'],params={'project_id':self.projects[0]}).json()['content'],text)
        result=self.search([row['id']],'kreyòl').json();self.assertTrue(result['evidence'])
        self.assertEqual(result['evidence'][0]['revision'],row['revision']);self.assertIn('kreyòl',result['evidence'][0]['excerpt'])
        self.assertEqual(self.search([row['id']],'PostgreSQL',self.projects[1]).status_code,404)
        self.assertEqual(self.client.get('/documents',params={'project_id':self.projects[1]}).json()['documents'],[])
        self.assertEqual(self.client.get('/documents/'+row['id'],params={'project_id':self.projects[1]}).status_code,404)
        self.assertEqual(self.search([row['id']],'no-match-needle').json()['evidence'],[])
        answer=self.search([row['id']],'PostgreSQL',endpoint='answer').json()
        self.assertEqual(answer['answer_kind'],'verbatim_evidence_excerpts_not_generated_claims')
        self.assertIn('[document:'+row['id']+'#chunk-',answer['answer'])
    def test_refresh_rebuilds_index_rejects_stale_review_and_delete_cascades(self):
        row=self.upload('Original obsoleteword source.')
        body=dict(name='notes.txt',kind='text',content='Replacement newword source.',expected_revision=row['revision'],confirmed=True)
        path='/documents/'+row['id'];params={'project_id':self.projects[0]}
        self.assertEqual(self.client.patch(path,params={'project_id':self.projects[1]},json=body).status_code,404)
        changed=self.client.patch(path,params=params,json=body);self.assertEqual(changed.status_code,200,changed.text)
        current=changed.json()['document'];self.assertNotEqual(current['revision'],row['revision'])
        self.assertEqual(self.search([row['id']],'obsoleteword').json()['evidence'],[])
        self.assertTrue(self.search([row['id']],'newword').json()['evidence'])
        self.assertEqual(self.client.patch(path,params=params,json=body).status_code,409)
        self.assertEqual(self.client.post(path+'/delete',params=params,json=dict(expected_revision=row['revision'],confirmed=True)).status_code,409)
        self.assertEqual(self.client.post(path+'/delete',params={'project_id':self.projects[1]},json=dict(expected_revision=current['revision'],confirmed=True)).status_code,404)
        self.assertEqual(self.client.post(path+'/delete',params=params,json=dict(expected_revision=current['revision'],confirmed=True)).status_code,200)
        with memory.connect() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM local_document_chunks WHERE document_id=%s',(uuid.UUID(row['id']),))
                self.assertIsNone(cur.fetchone())
    def test_simultaneous_refreshes_have_one_winner_and_old_revision_cannot_return(self):
        row=self.upload('Original source.')
        def refresh(content):
            return self.client.patch('/documents/'+row['id'],params={'project_id':self.projects[0]},
                json=dict(name=row['name'],kind='text',content=content,expected_revision=row['revision'],confirmed=True)).status_code
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(refresh,['First replacement','Second replacement']))
        self.assertEqual(sorted(statuses),[200,409])
        current=self.client.get('/documents/'+row['id'],params={'project_id':self.projects[0]}).json()['document']
        response=self.client.patch('/documents/'+row['id'],params={'project_id':self.projects[0]},
            json=dict(name=row['name'],kind='text',content='Original source.',expected_revision=current['revision'],confirmed=True))
        self.assertEqual(response.status_code,200);self.assertNotEqual(response.json()['document']['revision'],row['revision'])
    def test_literal_comparison_and_project_quota(self):
        a=self.upload('Shared line\nFirst exclusive');b=self.upload('Shared line\nSecond exclusive')
        compared=self.client.post('/documents/compare',params={'project_id':self.projects[0]},json=dict(document_ids=[a['id'],b['id']])).json()
        self.assertEqual(compared['common_unique_lines'],1);self.assertEqual(compared['unique_line_counts'],[1,1])
        self.assertFalse(compared['semantic_equivalence_checked'])
        for _ in range(28):self.upload('Quota fixture')
        response=self.client.post('/documents',params={'project_id':self.projects[0]},json=dict(name='extra.txt',kind='text',content='Extra',confirmed=True))
        self.assertEqual(response.status_code,409)
        self.assertEqual(len(self.client.get('/documents',params={'project_id':self.projects[0]}).json()['documents']),30)

if __name__=='__main__':unittest.main()
