import { parseDocumentAnswer } from './document-answer';
import type { OptionComparison } from '@/components/shy-comparison';
import type { ShyAgentResponse, ShyHealthResponse, ShyResearchAnswer, DocumentQuestion, ShyReplyPreferences, ResearchRequest } from './types';

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function toOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined;
}

export function parseReplyPreferences(value: unknown): ShyReplyPreferences | undefined {
  if (!isObject(value) || typeof value.status !== 'string' || !['enabled','disabled','not_configured','unavailable'].includes(value.status) || typeof value.applied_to_model_prompt !== 'boolean' || value.output_style_verified !== false) return undefined;
  if (value.applied_to_model_prompt && value.status !== 'enabled') return undefined;
  if (value.status === 'unavailable' ? value.revision !== null : (typeof value.revision !== 'string' || !/^(0|[1-9][0-9]{0,18})$/.test(value.revision))) return undefined;
  if (value.status === 'not_configured' && value.revision !== '0' || ['enabled','disabled'].includes(value.status) && value.revision === '0') return undefined;
  return {status:value.status as ShyReplyPreferences['status'],applied_to_model_prompt:value.applied_to_model_prompt,output_style_verified:false,revision:value.revision as string|null};
}

export function parseResearchRequest(value: unknown): ResearchRequest | undefined {
  if (!isObject(value) || typeof value.freshness !== 'string' || !['auto','same_day','past_week','past_month','any_date'].includes(value.freshness)) return undefined;
  return {freshness:value.freshness as ResearchRequest['freshness']};
}

export function parseResearchAnswer(value: unknown): ShyResearchAnswer | undefined {
  if (!isObject(value) || value.semantic_truth_verified !== false || typeof value.model_invoked !== 'boolean') return undefined;
  if (typeof value.mode !== 'string' || !['model_synthesis', 'missing_recent_evidence', 'missing_excerpts', 'possible_disagreement'].includes(value.mode)) return undefined;
  const mode = value.mode as ShyResearchAnswer['mode'];
  if (value.model_invoked !== (mode === 'model_synthesis')) return undefined;
  if (value.source_count !== undefined && (typeof value.source_count !== 'number' || !Number.isInteger(value.source_count) || value.source_count < 1 || value.source_count > 12)) return undefined;
  if (value.date_window_days !== undefined && value.date_window_days !== null && (typeof value.date_window_days !== 'number' || !Number.isInteger(value.date_window_days) || value.date_window_days < 0 || value.date_window_days > 3650)) return undefined;
  if (value.date_window_basis !== undefined && (typeof value.date_window_basis !== 'string' || !['english_hint','french_hint','haitian_creole_hint','mixed_hint','no_window','user_selected'].includes(value.date_window_basis) || (value.date_window_basis === 'user_selected' ? value.date_window_days !== null && ![0,7,30].includes(value.date_window_days as number) : value.date_window_basis === 'no_window' ? value.date_window_days !== null : ![0,7].includes(value.date_window_days as number)))) return undefined;
  return {
    mode, model_invoked: value.model_invoked, semantic_truth_verified: false,
    ...(typeof value.date_window_basis === 'string' ? {date_window_basis:value.date_window_basis as ShyResearchAnswer['date_window_basis']} : {}),
    ...(typeof value.source_count === 'number' ? { source_count: value.source_count } : {}),
    ...(value.date_window_days === null || typeof value.date_window_days === 'number' ? { date_window_days: value.date_window_days } : {}),
  };
}

export function parseShyAgentResponse(value: unknown): ShyAgentResponse {
  if (!isObject(value)) {
    throw new Error('Malformed SHY response.');
  }

  const status = value.status;
  if (typeof status !== 'string') {
    throw new Error('Malformed SHY response status.');
  }

  const response: ShyAgentResponse = {
    status: status as ShyAgentResponse['status'],
    assistant: toOptionalString(value.assistant),
    reason: toOptionalString(value.reason),
    message: toOptionalString(value.message),
    tool_name: toOptionalString(value.tool_name),
    tool_status: toOptionalString(value.tool_status),
    research_provider: toOptionalString(value.research_provider),
    research_answer: parseResearchAnswer(value.research_answer),
    reply_preferences: parseReplyPreferences(value.response_preferences),
    document_answer: parseDocumentAnswer(value.document_answer),
    conversation_id: toOptionalString(value.conversation_id),
    model: toOptionalString(value.model),
    provider: toOptionalString(value.provider),
    task_type: toOptionalString(value.task_type),
    routing_reason: toOptionalString(value.routing_reason),
    output: isObject(value.output) ? value.output : value.output === null ? null : undefined,
  };

  if (Array.isArray(value.sources)) {
    response.sources = value.sources
      .map((source) => {
        if (!isObject(source)) return null;
        const number = Number(source.number);
        if (!Number.isFinite(number)) return null;
        return {
          number,
          title: String(source.title ?? ''),
          url: String(source.url ?? ''),
          source: String(source.source ?? ''),
          ...(typeof source.source_date === 'string' ? { source_date: source.source_date.slice(0, 120) } : {}),
          ...(typeof source.retrieved_at === 'string' ? { retrieved_at: source.retrieved_at.slice(0, 120) } : {}),
          ...(typeof source.source_date_status === 'string' && ['unknown', 'invalid', 'future', 'recent', 'stale'].includes(source.source_date_status) ? { source_date_status: source.source_date_status } : {}),
          ...(source.date_basis === 'provider_publication_or_update_estimate' ? { date_basis: source.date_basis } : {}),
        };
      })
      .filter((source): source is NonNullable<ShyAgentResponse['sources']>[number] => source !== null);
  }

  return response;
}

export function parseShyHealthResponse(value: unknown): ShyHealthResponse {
  if (!isObject(value)) {
    throw new Error('Malformed health response.');
  }

  if (typeof value.status !== 'string' || typeof value.system !== 'string' || typeof value.version !== 'string') {
    throw new Error('Malformed health response.');
  }

  return {
    status: value.status,
    system: value.system,
    version: value.version,
    local_model: toOptionalString(value.local_model),
    application_healthy: typeof value.application_healthy === 'boolean' ? value.application_healthy : undefined,
    ollama_connected: typeof value.ollama_connected === 'boolean' ? value.ollama_connected : undefined,
    database_connected: typeof value.database_connected === 'boolean' ? value.database_connected : undefined,
    local_model_available: typeof value.local_model_available === 'boolean' ? value.local_model_available : undefined,
    model_backend: toOptionalString(value.model_backend),
    hosted_model: toOptionalString(value.hosted_model),
    research_configured: value.research_configured === true,
    hosted_model_configured: typeof value.hosted_model_configured === 'boolean' ? value.hosted_model_configured : undefined,
    hosted_model_inference_verified: typeof value.hosted_model_inference_verified === 'boolean' ? value.hosted_model_inference_verified : undefined,
  };
}

export function buildAgentRequest(
  message: string,
  conversationId?: string | null,
  clientUtcOffsetMinutes?: number,
  clientTimezone?: string,
  projectId?: string,
  optionComparison?: OptionComparison,
  documentQuestion?: DocumentQuestion,
  researchRequest?: ResearchRequest,
  allowCloudHistory = false
) {
  const body: {
    message: string;
    project_id?: string;
    option_comparison?: OptionComparison;
    document_question?: DocumentQuestion;
    research_request?: ResearchRequest;
    allow_cloud_history?: boolean;
    conversation_id?: string;
    client_utc_offset_minutes?: number;
    client_timezone?: string;
  } = { message };

  if (allowCloudHistory) body.allow_cloud_history = true;
  if (researchRequest) body.research_request = researchRequest;
  if (documentQuestion) body.document_question = documentQuestion;
  if (optionComparison) body.option_comparison = optionComparison;
  if (projectId) body.project_id = projectId;
  if (conversationId) {
    body.conversation_id = conversationId;
  }
  if (typeof clientUtcOffsetMinutes === 'number' && Number.isFinite(clientUtcOffsetMinutes)) {
    body.client_utc_offset_minutes = Math.trunc(clientUtcOffsetMinutes);
  }
  if (typeof clientTimezone === 'string' && clientTimezone.trim()) {
    body.client_timezone = clientTimezone.trim();
  }

  return body;
}

export function formatConversationTitle(message: string): string {
  const cleaned = message.trim().replace(/\s+/g, ' ');
  if (!cleaned) return 'New chat';
  const shortened = cleaned.slice(0, 52);
  return shortened.length < cleaned.length ? `${shortened.trimEnd()}…` : shortened;
}

