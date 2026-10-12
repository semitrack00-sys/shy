"""Real HTTP owner gateway checks; no model generation quality claim."""
import argparse
import base64
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

def check(base):
    password=os.environ['SHY_OWNER_PASSWORD']
    auth='Basic '+base64.b64encode(('owner:'+password).encode()).decode()
    def request(path,headers=None,body=None):
        req=Request(base+path,headers=headers or {},data=None if body is None else json.dumps(body).encode())
        try:
            with urlopen(req,timeout=15) as result:return result.status,result.read().decode()
        except HTTPError as exc:return exc.code,exc.read().decode()
    ready=False
    for _ in range(90):
        try:
            status,_=request('/livez')
            if status==200:ready=True;break
        except URLError:pass
        time.sleep(1)
    if not ready:raise RuntimeError('Hosted runtime did not become live')
    assert request('/')[0]==401
    status,html=request('/',{'Authorization':auth});assert status==200
    assert password not in html and os.environ['SHY_ACCESS_TOKEN'] not in html
    status,raw=request('/api/shy/health',{'Authorization':auth});assert status==200
    health=json.loads(raw);assert health['version']=='0.105.21' and health['database_connected'] is True
    assert health['ollama_connected'] is False and health['application_healthy'] is False
    body={'message':'Calculate 0.1 + 0.2','project_id':'hosted-deployment-check'}
    assert request('/api/shy/agent',body=body)[0]==401
    assert request('/api/shy/agent',{'Authorization':auth,'Origin':'https://wrong.example','Content-Type':'application/json'},body)[0]==403
    status,raw=request('/api/shy/agent',{'Authorization':auth,'Origin':base,'Content-Type':'application/json'},body)
    answer=json.loads(raw);assert status==200 and answer['status']=='RESPOND' and '0.3' in answer['message']
    assert answer['cognitive']['model_invoked'] is False
    print('PASS: real packaged hosted HTTP owner access, PostgreSQL health, rejected unauthorized/cross-site writes and deterministic calculator; model remains unavailable.')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8019');args=parser.parse_args();check(args.base_url.rstrip('/'))
