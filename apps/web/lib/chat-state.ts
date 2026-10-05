import { formatConversationTitle } from './shy-api';
import type { ChatMessage, ChatStore, ConversationThread, ShyAgentResponse } from './types';

export const STORAGE_KEY = 'shy.web.chat-store.v1';

export function createId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `shy-${Math.random().toString(36).slice(2, 10)}`;
}

export function createEmptyConversation(): ConversationThread {
  const now = new Date().toISOString();
  return {
    id: createId(),
    title: 'New chat',
    createdAt: now,
    updatedAt: now,
    conversationId: null,
    messages: [],
  };
}

export function createInitialStore(): ChatStore {
  const conversation = createEmptyConversation();
  return {
    conversations: [conversation],
    activeConversationId: conversation.id,
    theme: 'dark',
  };
}

export function makeUserMessage(content: string): ChatMessage {
  return {
    id: createId(),
    role: 'user',
    content,
    createdAt: new Date().toISOString(),
    status: 'sent',
  };
}

export function makeAssistantMessage(response: ShyAgentResponse): ChatMessage {
  return {
    id: createId(),
    role: 'assistant',
    content: response.message ?? response.reason ?? '',
    createdAt: new Date().toISOString(),
    status: 'sent',
    toolName: response.tool_name,
    toolStatus: response.tool_status,
    researchProvider: response.research_provider,
    sources: response.sources,
    responseStatus: response.status,
    output: response.output,
  };
}

export function makeFailureMessage(message: string): ChatMessage {
  return {
    id: createId(),
    role: 'assistant',
    content: message,
    createdAt: new Date().toISOString(),
    status: 'failed',
    responseStatus: 'FAILED',
    error: message,
  };
}

export function updateConversationFromMessage(conversation: ConversationThread, message: ChatMessage): ConversationThread {
  const messages = [...conversation.messages, message];
  const updatedAt = message.createdAt;
  const nextTitle = conversation.title === 'New chat' && message.role === 'user'
    ? formatConversationTitle(message.content)
    : conversation.title;

  return {
    ...conversation,
    title: nextTitle,
    updatedAt,
    lastUserMessage: message.role === 'user' ? message.content : conversation.lastUserMessage,
    messages,
  };
}

export function patchConversationResponse(conversation: ConversationThread, response: ShyAgentResponse, assistantMessage: ChatMessage): ConversationThread {
  return {
    ...conversation,
    conversationId: response.conversation_id ?? conversation.conversationId,
    updatedAt: assistantMessage.createdAt,
    messages: [...conversation.messages, assistantMessage],
  };
}

export function replaceConversation(conversations: ConversationThread[], updated: ConversationThread): ConversationThread[] {
  return conversations.map((conversation) => (conversation.id === updated.id ? updated : conversation));
}

export function upsertConversation(conversations: ConversationThread[], nextConversation: ConversationThread): ConversationThread[] {
  const index = conversations.findIndex((conversation) => conversation.id === nextConversation.id);
  if (index === -1) {
    return [nextConversation, ...conversations];
  }

  const next = conversations.slice();
  next[index] = nextConversation;
  next.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return next;
}

export function loadStore(storage: Storage | undefined): ChatStore {
  if (!storage) {
    return createInitialStore();
  }

  const raw = storage.getItem(STORAGE_KEY);
  if (!raw) {
    return createInitialStore();
  }

  try {
    const parsed = JSON.parse(raw) as Partial<ChatStore>;
    if (!Array.isArray(parsed.conversations) || typeof parsed.activeConversationId !== 'string' && parsed.activeConversationId !== null) {
      return createInitialStore();
    }
    return {
      conversations: parsed.conversations as ConversationThread[],
      activeConversationId: parsed.activeConversationId ?? parsed.conversations[0]?.id ?? null,
      theme: parsed.theme === 'light' || parsed.theme === 'dark' ? parsed.theme : 'dark',
    };
  } catch {
    return createInitialStore();
  }
}

export function saveStore(storage: Storage | undefined, store: ChatStore): void {
  if (!storage) return;
  storage.setItem(STORAGE_KEY, JSON.stringify(store));
}

export function searchConversations(conversations: ConversationThread[], query: string): ConversationThread[] {
  const needle = query.trim().toLocaleLowerCase();
  if (!needle) return conversations;
  return conversations.filter(conversation => conversation.title.toLocaleLowerCase().includes(needle)
    || conversation.messages.some(message => message.content.toLocaleLowerCase().includes(needle)));
}

export function renameConversation(conversations: ConversationThread[], id: string, title: string): ConversationThread[] {
  const trimmed = title.trim().slice(0, 100);
  if (!trimmed) return conversations;
  return conversations.map(conversation => conversation.id === id ? { ...conversation, title: trimmed } : conversation);
}
