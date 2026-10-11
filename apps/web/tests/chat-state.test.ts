import { describe, expect, it } from 'vitest';
import { createEmptyConversation, createInitialStore, makeAssistantMessage, makeUserMessage, patchConversationResponse, updateConversationFromMessage } from '../lib/chat-state';

describe('conversation state', () => {
  it('creates an initial empty store', () => {
    const store = createInitialStore();
    expect(store.conversations).toHaveLength(1);
    expect(store.activeConversationId).toBe(store.conversations[0].id);
  });

  it('generates a title from the first user message', () => {
    const conversation = createEmptyConversation();
    const next = updateConversationFromMessage(conversation, makeUserMessage('Explain in two sentences why the sky appears blue.'));
    expect(next.title).toBe('Explain in two sentences why the sky appears blue.');
    expect(next.lastUserMessage).toContain('sky appears blue');
  });

  it('stores assistant responses and backend conversation ids', () => {
    const conversation = createEmptyConversation();
    const next = updateConversationFromMessage(conversation, makeUserMessage('Hello'));
    const assistant = makeAssistantMessage({
      assistant: 'SHY',
      status: 'RESPOND',
      message: 'Hello back',
      conversation_id: 'backend-id',
    });

    const patched = patchConversationResponse(next, { assistant: 'SHY', status: 'RESPOND', message: 'Hello back', conversation_id: 'backend-id' }, assistant);

    expect(patched.conversationId).toBe('backend-id');
    expect(patched.messages).toHaveLength(2);
  });
});
it('preserves research context and sources across local history reload', async () => {
  const {loadStore,saveStore}=await import('../lib/chat-state');
  window.localStorage.clear();
  const store=createInitialStore();
  const assistant=makeAssistantMessage({status:'RESPOND',message:'Need evidence.',
    research_answer:{mode:'missing_recent_evidence',model_invoked:false,semantic_truth_verified:false,source_count:1,date_window_days:7},
    sources:[{number:1,title:'Source',url:'https://example.com',source:'example.com'}]});
  store.conversations[0].messages.push(assistant);
  saveStore(window.localStorage,store);
  const restored=loadStore(window.localStorage).conversations[0].messages[0];
  expect(restored.researchAnswer).toEqual(assistant.researchAnswer);
  expect(restored.sources).toEqual(assistant.sources);
  window.localStorage.clear();
});
