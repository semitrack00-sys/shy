import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/core'))
from deployment_access import DeploymentAccess
class Access(unittest.TestCase):
    def setUp(self):
        app=FastAPI();app.add_middleware(DeploymentAccess)
        @app.get('/private')
        async def private():return {'private':'data'}
        @app.post('/write')
        async def write():raise AssertionError('Unauthorized writes must not run')
        self.client=TestClient(app)
    def test_local_defaults_and_hosted_missing_configuration_fail_closed(self):
        with patch.dict(os.environ,{'RENDER':'','SHY_REQUIRE_AUTH':'','SHY_ACCESS_TOKEN':''}):
            self.assertEqual(self.client.get('/private').status_code,200)
        with patch.dict(os.environ,{'SHY_REQUIRE_AUTH':'1','SHY_ACCESS_TOKEN':''}):
            self.assertEqual(self.client.get('/private').status_code,503)
            self.assertEqual(self.client.get('/livez').json(),{'status':'alive','system':'SHY'})
            self.assertEqual(self.client.post('/write').status_code,503)
    def test_owner_bearer_and_no_query_string_authentication(self):
        token='a'*40
        with patch.dict(os.environ,{'SHY_REQUIRE_AUTH':'1','SHY_ACCESS_TOKEN':token}):
            for headers in [{},{'authorization':'Bearer wrong'},{'authorization':'Basic '+token}]:
                self.assertEqual(self.client.get('/private',headers=headers).status_code,401)
                self.assertEqual(self.client.post('/write',headers=headers).status_code,401)
            self.assertEqual(self.client.get('/private?token='+token).status_code,401)
            response=self.client.get('/private',headers={'authorization':'Bearer '+token})
            self.assertEqual(response.status_code,200);self.assertEqual(response.json(),{'private':'data'})
            self.assertEqual(self.client.get('/openapi.json').status_code,401)
if __name__=='__main__':unittest.main()
