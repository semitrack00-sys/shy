import React from 'react';
import { fireEvent, render, screen, waitFor, cleanup } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ShyShell } from '../components/shy-shell';
afterEach(()=>{cleanup();window.localStorage.clear();vi.unstubAllGlobals();});
it('shares thread context only after explicit consent and refreshes model status after a reply',async()=>{
  window.localStorage.clear();Element.prototype.scrollIntoView=vi.fn();
  const requests: Record<string,unknown>[]=[];
  let healthCalls=0;
  vi.stubGlobal('fetch',vi.fn(async (url:string,options?:RequestInit)=>{
    if(url.endsWith('/health')){healthCalls++;return new Response(JSON.stringify({status:'degraded',system:'SHY',version:'0.105.25',model_backend:'runpod',hosted_model:'qwen/qwen3.5-4b',hosted_model_configured:true,hosted_model_inference_verified:healthCalls>1}));}
    if(url.endsWith('/agent')){requests.push(JSON.parse(String(options?.body)));return new Response(JSON.stringify({status:'RESPOND',message:'Hello.',conversation_id:'11111111-1111-4111-8111-111111111111'}));}
    return new Response('{}');
  }));
  render(<ShyShell/>);
  const checkbox=await screen.findByLabelText('Allow RunPod to use this chat’s recent messages for follow-ups');
  expect(checkbox).not.toBeChecked();
  fireEvent.change(screen.getByLabelText('Message SHY'),{target:{value:'Hello'}});
  fireEvent.click(screen.getByRole('button',{name:'Send',exact:true}));
  await waitFor(()=>expect(healthCalls).toBe(2));
  expect(requests[0]).not.toHaveProperty('allow_cloud_history');
  fireEvent.click(checkbox);
  fireEvent.change(screen.getByLabelText('Message SHY'),{target:{value:'What did I say?'}});
  fireEvent.click(screen.getByRole('button',{name:'Send',exact:true}));
  await waitFor(()=>expect(requests).toHaveLength(2));
  expect(requests[1]).toMatchObject({allow_cloud_history:true,conversation_id:'11111111-1111-4111-8111-111111111111'});
  await waitFor(()=>expect(healthCalls).toBe(3));
  fireEvent.click(screen.getByRole('button',{name:'New chat',exact:true}));
  expect(screen.getByLabelText('Allow RunPod to use this chat’s recent messages for follow-ups')).not.toBeChecked();
});
