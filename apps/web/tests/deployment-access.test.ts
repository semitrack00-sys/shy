import { webcrypto } from 'node:crypto';
import { afterEach, expect, it, vi } from 'vitest';
import { NextRequest } from 'next/server';
import { getBackendHeaders, ownerAuthorized } from '@/lib/deployment-access';
import { middleware } from '../middleware';
afterEach(()=>{vi.unstubAllEnvs();vi.unstubAllGlobals();});
function configured(){vi.stubGlobal('crypto',webcrypto);vi.stubEnv('SHY_REQUIRE_AUTH','1');vi.stubEnv('SHY_OWNER_USERNAME','owner');vi.stubEnv('SHY_OWNER_PASSWORD','p'.repeat(32));vi.stubEnv('SHY_ACCESS_TOKEN','t'.repeat(40));vi.stubEnv('SHY_PUBLIC_ORIGIN','https://shy.example');}
it('requires owner authentication on pages and API routes',async()=>{
  configured();expect(await ownerAuthorized(null)).toBe(false);expect(await ownerAuthorized('Basic bad')).toBe(false);
  expect(await ownerAuthorized('Basic '+btoa('owner:'+'p'.repeat(32)))).toBe(true);
  expect(await ownerAuthorized('Basic '+btoa('owner:wrong'))).toBe(false);
  for(const path of ['/','/api/shy/agent','/_next/static/file.js'])expect((await middleware(new NextRequest('https://shy.example'+path))).status).toBe(401);
});
it('rejects cross-site writes and keeps credentials in server-side headers',async()=>{
  configured();const authorization='Basic '+btoa('owner:'+'p'.repeat(32));
  for(const origin of [undefined,'https://evil.example'])expect((await middleware(new NextRequest('https://shy.example/api/shy/agent',{method:'POST',headers:{authorization,...(origin?{origin}:{})}}))).status).toBe(403);
  const response=await middleware(new NextRequest('https://shy.example/api/shy/agent',{method:'POST',headers:{authorization,origin:'https://shy.example'}}));
  expect(response.status).toBe(200);expect(response.headers.get('cache-control')).toBe('private, no-store');expect(response.headers.get('authorization')).toBeNull();
  expect(getBackendHeaders()).toEqual({authorization:'Bearer '+'t'.repeat(40)});
});
it('fails closed for missing hosted secrets and preserves local development defaults',async()=>{
  configured();vi.stubEnv('SHY_ACCESS_TOKEN','');expect(()=>getBackendHeaders()).toThrow();expect((await middleware(new NextRequest('https://shy.example/'))).status).toBe(503);
  vi.stubEnv('SHY_REQUIRE_AUTH','');vi.stubEnv('RENDER','');vi.stubEnv('SHY_OWNER_PASSWORD','');
  expect(getBackendHeaders()).toEqual({});expect((await middleware(new NextRequest('http://localhost/'))).status).toBe(200);
});

it('uses Render provided origin and returns only minimal public liveness',async()=>{
  configured();vi.stubEnv('SHY_PUBLIC_ORIGIN','');vi.stubEnv('RENDER_EXTERNAL_URL','https://shy.render.example');
  const response=await middleware(new NextRequest('https://shy.render.example/livez'));
  expect(response.status).toBe(200);expect(await response.json()).toEqual({status:'alive',system:'SHY'});
  expect((await middleware(new NextRequest('https://shy.render.example/health'))).status).toBe(401);
});

it('accepts eight-character owner passwords and rejects shorter or incorrect passwords',async()=>{
  configured();vi.stubEnv('SHY_OWNER_PASSWORD','fixture8');
  const authorization='Basic '+btoa('owner:fixture8');
  expect(await ownerAuthorized(authorization)).toBe(true);
  expect(await ownerAuthorized('Basic '+btoa('owner:incorrect'))).toBe(false);
  expect((await middleware(new NextRequest('https://shy.example/',{headers:{authorization}}))).status).toBe(200);
  expect((await middleware(new NextRequest('https://shy.example/'))).status).toBe(401);
  vi.stubEnv('SHY_OWNER_PASSWORD','short77');
  expect(await ownerAuthorized('Basic '+btoa('owner:short77'))).toBe(false);
  expect((await middleware(new NextRequest('https://shy.example/'))).status).toBe(503);
});
