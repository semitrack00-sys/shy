"""Disposable PostgreSQL checks for exact saved values, excerpt provenance and isolation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'services/core'))
FIXTURE=ROOT/'docs/examples/local-data-benchmark.json'


def run_benchmark():
    if not os.environ.get('DATABASE_URL'):
        raise RuntimeError('DATABASE_URL must point to a disposable PostgreSQL database')
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import documents,memory,memory_controls
    raw=FIXTURE.read_bytes();fixture=json.loads(raw)
    memory.ensure_memory_schema();documents.ensure_document_schema()
    app=FastAPI();app.include_router(memory_controls.router);app.include_router(documents.router)
    app.add_middleware(memory_controls.MemoryBodyLimit);app.add_middleware(documents.DocumentBodyLimit)
    client=TestClient(app);projects=['bench-'+uuid.uuid4().hex,'bench-other-'+uuid.uuid4().hex];results=[]
    def record(name,actual,expected):
        results.append({'id':name,'passed':actual==expected,'actual':actual,'expected':expected})
    try:
        a,b=({'project_id':p} for p in projects)
        for item in fixture['memories']:
            body={key:item[key] for key in ['subject_key','category','content']}
            initial=client.post('/memories/preview',params=a,json=body)
            record(item['id']+'-new',initial.json().get('status'),'new_subject')
            saved=client.post('/memories',params=a,json={**body,'confirmed':True})
            record(item['id']+'-save-status',saved.status_code,201)
            row=saved.json()['record']
            exact=client.post('/memories/preview',params=a,json=body).json()
            record(item['id']+'-exact',exact.get('status'),'same_saved_value')
            record(item['id']+'-no-write',exact.get('saved'),False)
            record(item['id']+'-isolated',client.post('/memories/preview',params=b,json=body).json().get('status'),'new_subject')
            proposed={**body,'content':item['corrected']}
            preview=client.post('/memories/preview',params=a,json=proposed).json()
            record(item['id']+'-review',preview.get('status'),'review_required')
            record(item['id']+'-retains-old',preview['records'][0]['content'],item['content'])
            correction={'content':item['corrected'],'expected_revision':row['revision'],'confirmed':True}
            record(item['id']+'-cross-project-correction',client.patch('/memories/'+row['id'],params=b,json=correction).status_code,404)
            changed=client.patch('/memories/'+row['id'],params=a,json=correction)
            record(item['id']+'-correction',changed.json().get('record',{}).get('content'),item['corrected'])
            record(item['id']+'-stale',client.patch('/memories/'+row['id'],params=a,json={**correction,'content':'Stale overwrite'}).status_code,409)
        for item in fixture['documents']:
            response=client.post('/documents',params=a,json={'name':item['name'],'kind':item['kind'],'content':item['content'],'confirmed':True})
            record(item['id']+'-save-status',response.status_code,201)
            row=response.json()['document'];body={'document_ids':[row['id']],'query':item['query'],'limit':5}
            answer=client.post('/documents/answer',params=a,json=body).json()
            record(item['id']+'-found',answer.get('found_evidence'),True)
            record(item['id']+'-extractive',answer.get('answer_kind'),'verbatim_evidence_excerpts_not_generated_claims')
            record(item['id']+'-exact-text',item['expected_excerpt'] in answer.get('answer',''),True)
            record(item['id']+'-revision',all(e['revision']==row['revision'] for e in answer['evidence']),True)
            record(item['id']+'-provenance',all(e['excerpt'] in item['content'] for e in answer['evidence']),True)
            record(item['id']+'-cross-project',client.post('/documents/answer',params=b,json=body).status_code,404)
            missing=client.post('/documents/answer',params=a,json={**body,'query':'absentneedlezz'}).json()
            record(item['id']+'-missing',missing.get('found_evidence'),False)
    finally:
        # Delete only the uniquely generated benchmark project records.
        with memory.connect() as conn:
            with conn.cursor() as cur:
                for project in projects:
                    owner=memory.local_memory_user(project)
                    cur.execute('DELETE FROM local_documents WHERE user_id=%s',(owner,))
                    cur.execute('DELETE FROM durable_memories WHERE user_id=%s',(owner,))
                    cur.execute('DELETE FROM users WHERE id=%s',(owner,))
        client.close()
    return {'benchmark':'local_supplied_data_v1','fixture_sha256':hashlib.sha256(raw).hexdigest(),
            'case_count':len(results),'passed_count':sum(r['passed'] for r in results),'results':results,
            'representative_language_accuracy_measured':False,'generated_answer_accuracy_measured':False,
            'real_account_authentication_tested':False,'qualification_complete':False}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',required=True);args=parser.parse_args()
    try:report=run_benchmark()
    except RuntimeError as exc:print(str(exc),file=sys.stderr);return 2
    destination=Path(args.report);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f"Local data checks: {report['passed_count']}/{report['case_count']}; broad answer accuracy remains unqualified.")
    return 0 if report['passed_count']==report['case_count'] else 1
if __name__=='__main__':sys.exit(main())
