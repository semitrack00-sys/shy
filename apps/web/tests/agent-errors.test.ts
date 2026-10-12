import { afterEach, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { POST } from '../app/api/shy/agent/route';
import { parseShyAgentResponse } from '../lib/shy-api';
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); });
async function proxy(status: number, body: string) {
  vi.stubEnv('SHY_REQUIRE_AUTH', ''); vi.stubEnv('RENDER', ''); vi.stubEnv('SHY_ACCESS_TOKEN', '');
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {status})));
  return POST(new NextRequest('http://localhost/api/shy/agent', {method:'POST', body:'{"message":"hello"}'}));
}
it('displays a readable startup timeout instead of a malformed response error', async () => {
  const detail = 'The cloud model did not finish starting or answering in time. Please try again.';
  const response = await proxy(503, JSON.stringify({detail}));
  expect(response.status).toBe(503);
  expect(parseShyAgentResponse(await response.json())).toMatchObject({status:'FAILED', reason:detail});
});
it('does not expose unknown errors, credentials, or invalid upstream responses', async () => {
  for (const body of ['{"detail":"Bearer secret-key"}', '<html>private credentials</html>', '{"detail":'+JSON.stringify('x'.repeat(5000))+'}']) {
    const response = await proxy(401, body);
    expect(await response.json()).toEqual({assistant:'SHY', status:'FAILED', reason:'SHY is temporarily unavailable. Please try again.'});
  }
});
it('preserves successful chat replies', async () => {
  const body = JSON.stringify({assistant:'SHY', status:'COMPLETED', message:'Paris.'});
  expect(await (await proxy(200, body)).text()).toBe(body);
});
