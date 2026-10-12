import asyncio,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'services/core'))
from pydantic import ValidationError
import response_preferences as prefs
from fastapi import FastAPI
from fastapi.testclient import TestClient
BASE={'enabled':True,'language':'ht','detail':'short','tone':'plain','expected_revision':'0','confirmed':True}
class Preferences(unittest.TestCase):
    def test_only_reviewed_enum_preferences_and_no_prompt_override(self):
        self.assertEqual(prefs.PreferenceChange(**BASE).language,'ht')
        for patch_data in [{'language':'ignore rules'},{'detail':'print secrets'},{'tone':'unsafe'},{'enabled':1},{'confirmed':1},{'confirmed':False},{'system_prompt':'override'},{'expected_revision':'-1'}]:
            with self.assertRaises(ValidationError):prefs.PreferenceChange(**{**BASE,**patch_data})
    def test_mapped_guidance_and_context_reset_including_failure(self):
        profile={**BASE,'revision':'1','reviewed':True}
        async def handler(_):
            self.assertTrue(prefs.local_generation_required());text=prefs.prompt_guidance();self.assertIn('Haitian Creole',text);self.assertIn('explicit instructions take precedence',text);return {'message':'Fixture'}
        with patch.object(prefs,'read',return_value=profile):
            result=asyncio.run(prefs.with_preferences(None,handler,'owner'))
        self.assertTrue(result['response_preferences']['applied_to_model_prompt']);self.assertFalse(result['response_preferences']['output_style_verified']);self.assertIsNone(prefs.current_preferences.get())
        async def failing(_):prefs.prompt_guidance();raise RuntimeError('fixture')
        with patch.object(prefs,'read',return_value=profile),self.assertRaises(RuntimeError):asyncio.run(prefs.with_preferences(None,failing,'owner'))
        self.assertIsNone(prefs.current_preferences.get());self.assertEqual(prefs.prompt_guidance(),'')
    def test_concurrent_scopes_and_unavailable_database_do_not_leak(self):
        async def run():
            async def handler(owner):
                await asyncio.sleep(0);return {'message':prefs.prompt_guidance()}
            with patch.object(prefs,'read',side_effect=lambda owner:{**BASE,'revision':'1','reviewed':True,'language':owner}):
                return await asyncio.gather(prefs.with_preferences('ht',handler,'ht'),prefs.with_preferences('fr',handler,'fr'))
        left,right=asyncio.run(run());self.assertIn('Haitian Creole',left['message']);self.assertIn('French',right['message']);self.assertNotIn('French',left['message'])
        async def handler(_):return {'message':prefs.prompt_guidance()}
        with patch.object(prefs,'read',side_effect=RuntimeError('private secret')):data=asyncio.run(prefs.with_preferences(None,handler,'owner'))
        self.assertEqual(data['message'],'');self.assertEqual(data['response_preferences']['status'],'unavailable');self.assertNotIn('secret',str(data));self.assertIsNone(prefs.current_preferences.get())
    def test_generic_api_database_failure_is_safe(self):
        app=FastAPI();app.include_router(prefs.router);client=TestClient(app)
        with patch.object(prefs.memory,'connect',side_effect=RuntimeError('private secret')):
            for method,body in [('GET',None),('PATCH',BASE)]:
                response=client.request(method,'/memories/response-preferences',**({'json':body} if body else {}))
                self.assertEqual(response.status_code,503,response.text);self.assertNotIn('secret',response.text)
if __name__=='__main__':unittest.main()
