"""Public endpoint contract, fail-closed privacy, and single-submission checks."""
from test_runpod_provider import module, types
import os
import json
import httpx
from unittest.mock import patch


def run():
    real_client = httpx.Client
    calls = []
    def handle(req):
        calls.append(req)
        return httpx.Response(200, json={'choices':[{'message':{'content':'\n</think>\nHello!'},'finish_reason':'stop'}]})
    env = {'SHY_RUNPOD_MODE':'public','SHY_RUNPOD_API_KEY':'fixture-secret','SHY_RUNPOD_ENDPOINT_ID':''}
    with patch.dict(os.environ, env), patch.object(module.httpx, 'Client', side_effect=lambda **kw:real_client(transport=httpx.MockTransport(handle), **kw)):
        p = module.RunPodProvider()
        req = types.ModelRequest(messages=(types.ModelMessage('system','Be concise.'), types.ModelMessage('user','Hello')), capability=types.ModelCapability.CHAT, max_output_tokens=9000)
        assert p.configured and p.model_id == 'Qwen/Qwen3-32B-AWQ'
        assert p.generate(req,p.model_id).content == 'Hello!'
        assert len(calls) == 1
        sent = calls[0]
        assert str(sent.url) == 'https://api.runpod.ai/v2/qwen3-32b-awq/openai/v1/chat/completions'
        body = json.loads(sent.content)
        assert body['max_tokens'] == 512 and body['chat_template_kwargs'] == {'enable_thinking':False}
        assert [m['role'] for m in body['messages']] == ['system','user']
        for privacy in ('LOCAL_ONLY','PRIVATE_REMOTE_ALLOWED'):
            private = types.ModelRequest(messages=req.messages,capability=req.capability,metadata={'privacy_requirement':privacy})
            try:
                p.generate(private,p.model_id)
                raise AssertionError('Private data transmitted')
            except ValueError:
                pass
        assert len(calls) == 1
    for failure in (401, 429, 500, 'timeout'):
        calls.clear()
        def fail(req):
            calls.append(req)
            if failure == 'timeout':
                raise httpx.ReadTimeout('fixture-secret', request=req)
            return httpx.Response(failure, text='fixture-secret')
        with patch.dict(os.environ,env), patch.object(module.httpx,'Client',side_effect=lambda **kw:real_client(transport=httpx.MockTransport(fail),**kw)):
            p = module.RunPodProvider()
            try:
                p.generate(req,p.model_id)
                raise AssertionError('Failure accepted')
            except module.HostedInferenceError as exc:
                assert 'fixture-secret' not in str(exc)
                assert exc.code == ('timeout' if failure == 'timeout' else 'unavailable')
            assert len(calls) == 1 and not p.retry_ready
    with patch.dict(os.environ,{**env,'SHY_RUNPOD_MODE':'typo'}):
        assert not module.RunPodProvider().configured
    print('Public endpoint transport, privacy, limits, and failure checks passed')

if __name__ == '__main__':
    run()
