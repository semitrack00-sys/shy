export type ShyAgentStatus = 'RESPOND' | 'TOOL_RESULT' | 'FAILED' | 'AWAITING_APPROVAL' | 'INVALID_APPROVAL' | 'DENIED' | 'UNAVAILABLE' | 'BLOCKED' | 'CANCELLED';

export interface ShyResearchSource {
  number: number;
  title: string;
  url: string;
  source: string;
  source_date?: string;
  retrieved_at?: string;
  source_date_status?: string;
  date_basis?: string;
}

export interface ShyResearchAnswer {
  mode: 'model_synthesis' | 'missing_recent_evidence' | 'missing_excerpts' | 'possible_disagreement';
  model_invoked: boolean;
  semantic_truth_verified: false;
  source_count?: number;
  date_window_days?: number | null;
  date_window_basis?: 'english_hint' | 'french_hint' | 'haitian_creole_hint' | 'mixed_hint' | 'no_window' | 'user_selected';
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
  reply_preferences?: ShyReplyPreferences;
  research_answer?: ShyResearchAnswer;
  document_answer?: ShyDocumentAnswer;
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
  application_healthy?: boolean;
  ollama_connected?: boolean;
  database_connected?: boolean;
  local_model_available?: boolean;
  model_backend?: string;
  hosted_model?: string;
  hosted_model_configured?: boolean;
  research_configured?: boolean;
  hosted_model_inference_verified?: boolean;
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
  replyPreferences?: ShyReplyPreferences;
  researchAnswer?: ShyResearchAnswer;
  documentAnswer?: ShyDocumentAnswer;
  documentQuestion?: DocumentQuestion;
  researchRequest?: ResearchRequest;
  researchQuery?: string;
  sources?: ShyResearchSource[];
  responseStatus?: ShyAgentStatus;
  output?: ShyToolOutput | null;
  error?: string;
}

export interface ConversationThread {
  projectId?: string;
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


export interface DocumentQuestion { document_ids: string[]; query: string; limit?: number; answer_mode?: 'excerpts' | 'local_answer'; confirmed_local_generation?: boolean }
export interface ShyDocumentAnswer {
  method: 'local_keyword_search'; answer_kind: 'verbatim_evidence_excerpts_not_generated_claims' | 'model_answer_from_selected_excerpts';
  model_invoked: boolean; semantic_support_verified: false;
  citation_membership_checked?: true; cited_source_numbers?: number[]; found_evidence: boolean;
  selected_documents: string[];
  evidence: {number?:number;document_id:string;name:string;revision:string;chunk:number;start_line:number;end_line:number;excerpt:string}[];
}

export interface ShyReplyPreferences {
  status:'enabled'|'disabled'|'not_configured'|'unavailable';
  applied_to_model_prompt:boolean; output_style_verified:false; revision:string|null;
}

export interface ResearchRequest { freshness: 'auto' | 'same_day' | 'past_week' | 'past_month' | 'any_date' }
