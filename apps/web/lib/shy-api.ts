import type { ShyAgentResponse, ShyHealthResponse } from './types';

export function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

export function toOptionalString(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim().length > 0 ? value : undefined;
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
    active_model: toOptionalString(value.active_model),
    inference_provider: toOptionalString(value.inference_provider),
    inference_connected: typeof value.inference_connected === 'boolean' ? value.inference_connected : undefined,
    ollama_connected: typeof value.ollama_connected === 'boolean' ? value.ollama_connected : undefined,
    remote_inference_connected: typeof value.remote_inference_connected === 'boolean' ? value.remote_inference_connected : undefined,
    database_connected: typeof value.database_connected === 'boolean' ? value.database_connected : undefined,
    local_model_available: typeof value.local_model_available === 'boolean' ? value.local_model_available : undefined,
    remote_model_available: typeof value.remote_model_available === 'boolean' ? value.remote_model_available : undefined,
    model_available: typeof value.model_available === 'boolean' ? value.model_available : undefined,
    application_healthy: typeof value.application_healthy === 'boolean' ? value.application_healthy : undefined,
  };
}

export function buildAgentRequest(message: string, conversationId?: string | null) {
  return conversationId ? { message, conversation_id: conversationId } : { message };
}

export function formatConversationTitle(message: string): string {
  const cleaned = message.trim().replace(/\s+/g, ' ');
  if (!cleaned) return 'New chat';
  const shortened = cleaned.slice(0, 52);
  return shortened.length < cleaned.length ? `${shortened.trimEnd()}…` : shortened;
}