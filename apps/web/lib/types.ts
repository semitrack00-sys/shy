export type ShyAgentStatus = 'RESPOND' | 'TOOL_RESULT' | 'FAILED' | 'AWAITING_APPROVAL' | 'INVALID_APPROVAL' | 'DENIED' | 'UNAVAILABLE';

export interface ShyResearchSource {
  number: number;
  title: string;
  url: string;
  source: string;
}

export interface ShyToolOutput {
  [key: string]: unknown;
}

export interface ShyAgentResponse {
  assistant?: string;
  status: ShyAgentStatus;
  reason?: string;
  message?: string;
  tool_name?: string;
  tool_status?: string;
  research_provider?: string;
  sources?: ShyResearchSource[];
  output?: ShyToolOutput | null;
  conversation_id?: string;
  model?: string;
  provider?: string;
  task_type?: string;
  routing_reason?: string;
}

export interface ShyHealthResponse {
  status: string;
  system: string;
  version: string;
  local_model?: string;
  ollama_connected?: boolean;
  database_connected?: boolean;
}

export type MessageRole = 'user' | 'assistant';

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  createdAt: string;
  status?: 'sending' | 'sent' | 'failed';
  toolName?: string;
  toolStatus?: string;
  researchProvider?: string;
  sources?: ShyResearchSource[];
  responseStatus?: ShyAgentStatus;
  output?: ShyToolOutput | null;
  error?: string;
}

export interface ConversationThread {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  conversationId: string | null;
  messages: ChatMessage[];
  lastUserMessage?: string;
}

export interface ChatStore {
  conversations: ConversationThread[];
  activeConversationId: string | null;
  theme: 'light' | 'dark';
}