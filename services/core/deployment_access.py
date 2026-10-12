"""Owner-only hosted access; local installations keep their existing defaults."""
import json
import os
import secrets

class DeploymentAccess:
    def __init__(self, app): self.app=app
    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        token=os.getenv('SHY_ACCESS_TOKEN','')
        required=os.getenv('SHY_REQUIRE_AUTH','')=='1' or os.getenv('RENDER','').lower()=='true' or bool(token)
        if scope.get('path')=='/livez' and scope.get('method')=='GET':
            return await self.reply(send,200,{'status':'alive','system':'SHY'})
        if not required: return await self.app(scope,receive,send)
        if len(token)<32:
            return await self.reply(send,503,{'detail':'hosted_access_not_configured'})
        supplied=dict(scope.get('headers',[])).get(b'authorization',b'')
        expected=('Bearer '+token).encode('utf-8')
        if not secrets.compare_digest(supplied,expected):
            return await self.reply(send,401,{'detail':'owner_access_required'})
        return await self.app(scope,receive,send)
    @staticmethod
    async def reply(send,status,body):
        await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json'),(b'cache-control',b'no-store')]})
        await send({'type':'http.response.body','body':json.dumps(body).encode()})
