import { expect, it } from 'vitest';
import { createEmptyConversation, loadStore, makeUserMessage, updateConversationFromMessage } from '@/lib/chat-state';
import { buildAgentRequest } from '@/lib/shy-api';

it('keeps project scope through message updates, persistence and request construction', () => {
  const original = createEmptyConversation('gud-express');
  const conversation = updateConversationFromMessage(original, makeUserMessage('Remember our project configuration'));
  expect(conversation.projectId).toBe('gud-express');
  const storage = { getItem: () => JSON.stringify({ conversations:[conversation], activeConversationId:conversation.id, theme:'dark' }) } as unknown as Storage;
  const loaded = loadStore(storage).conversations[0];
  expect(buildAgentRequest('Hello', loaded.conversationId, -420, 'America/Los_Angeles', loaded.projectId).project_id).toBe('gud-express');
  expect(buildAgentRequest('Hello')).not.toHaveProperty('project_id');
});
