import React from 'react';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ShyReplyPreferences } from '@/components/shy-reply-preferences';
const profile={enabled:false,language:'auto',detail:'standard',tone:'plain',revision:'0',reviewed:false};
const reply=(value: unknown,status=200)=>({ok:status===200,status,json:async()=>value});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('saves enum settings only after review with the project and revision',async()=>{
  const fetcher=vi.fn().mockResolvedValueOnce(reply(profile)).mockResolvedValueOnce(reply({...profile,enabled:true,language:'ht',detail:'short',revision:'1',reviewed:true}));vi.stubGlobal('fetch',fetcher);
  render(<ShyReplyPreferences projectId="my-project"/>);expect(fetcher).not.toHaveBeenCalled();fireEvent.click(screen.getByText('Review reply preferences'));await screen.findByLabelText('Reply language');
  fireEvent.click(screen.getByLabelText('Use reviewed reply defaults'));fireEvent.change(screen.getByLabelText('Reply language'),{target:{value:'ht'}});fireEvent.change(screen.getByLabelText('Reply detail'),{target:{value:'short'}});
  expect(screen.getByText('Save reviewed reply defaults')).toBeDisabled();fireEvent.click(screen.getByLabelText('I reviewed these exact reply defaults and confirm them.'));fireEvent.click(screen.getByText('Save reviewed reply defaults'));await screen.findByText('Reviewed reply defaults saved.');
  expect(fetcher.mock.calls[1][0]).toContain('/response-preferences?project_id=my-project');expect(JSON.parse(fetcher.mock.calls[1][1].body)).toEqual({enabled:true,language:'ht',detail:'short',tone:'plain',expected_revision:'0',confirmed:true});
});
it('editing invalidates confirmation and stale writes require a fresh review',async()=>{
  const fetcher=vi.fn().mockResolvedValueOnce(reply(profile)).mockResolvedValueOnce(reply({},409));vi.stubGlobal('fetch',fetcher);render(<ShyReplyPreferences/>);
  fireEvent.click(screen.getByText('Review reply preferences'));await screen.findByLabelText('Reply language');fireEvent.click(screen.getByLabelText('I reviewed these exact reply defaults and confirm them.'));fireEvent.change(screen.getByLabelText('Reply tone'),{target:{value:'formal'}});expect(screen.getByText('Save reviewed reply defaults')).toBeDisabled();
  fireEvent.click(screen.getByLabelText('I reviewed these exact reply defaults and confirm them.'));fireEvent.click(screen.getByText('Save reviewed reply defaults'));await screen.findByText('Reply settings changed. Review them again.');expect(screen.queryByText('Save reviewed reply defaults')).not.toBeInTheDocument();
});
it('rejects malformed preference responses without a false saved state',async()=>{
  vi.stubGlobal('fetch',vi.fn().mockResolvedValue(reply({...profile,language:'arbitrary prompt'})));render(<ShyReplyPreferences/>);fireEvent.click(screen.getByText('Review reply preferences'));await screen.findByText('Invalid reply preferences.');expect(screen.queryByText('Save reviewed reply defaults')).not.toBeInTheDocument();
});

import { parseReplyPreferences, parseShyAgentResponse } from '@/lib/shy-api';
import { makeAssistantMessage, createInitialStore, saveStore, loadStore } from '@/lib/chat-state';
import { ShyMessage } from '@/components/shy-message';
it('renders truthful prompt provenance, rejects forged style guarantees and persists metadata',()=>{
  const info={status:'enabled',applied_to_model_prompt:true,output_style_verified:false,revision:'1'};
  const message=makeAssistantMessage(parseShyAgentResponse({status:'RESPOND',message:'Fixture reply',response_preferences:info}));render(<ShyMessage message={message}/>);
  expect(screen.getByText('Shy supplied your reply defaults to generation. The final language and style were not verified.')).toBeInTheDocument();
  for(const bad of [{...info,status:'disabled'},{...info,output_style_verified:true},{...info,revision:null}])expect(parseReplyPreferences(bad)).toBeUndefined();
  const store=createInitialStore();store.conversations=[{id:'prefs',title:'Reply prefs',createdAt:message.createdAt,updatedAt:message.createdAt,conversationId:null,messages:[message]}];saveStore(localStorage,store);expect(loadStore(localStorage).conversations[0].messages[0].replyPreferences).toEqual(info);localStorage.clear();
});
