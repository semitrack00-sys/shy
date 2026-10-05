import { describe, expect, it } from 'vitest';
import { buildAgentRequest, formatConversationTitle, parseShyAgentResponse, parseShyHealthResponse } from '../lib/shy-api';

describe('SHY API parsing', () => {
  it('parses structured agent responses', () => {
    const response = parseShyAgentResponse({
      assistant: 'SHY',
      status: 'RESPOND',
      reason: 'ok',
      message: 'Hello',
      tool_name: 'web.search',
      tool_status: 'EXECUTED',
      research_provider: 'tavily',
      sources: [
        { number: 1, title: 'Source One', url: 'https://example.com', source: 'example.com' },
      ],
      conversation_id: 'abc',
      model: 'qwen3.5:4b',
      provider: 'ollama-local',
      task_type: 'research_synthesis',
      routing_reason: 'research',
    });

    expect(response.status).toBe('RESPOND');
    expect(response.sources?.[0].title).toBe('Source One');
    expect(response.research_provider).toBe('tavily');
  });

  it('rejects malformed agent responses', () => {
    expect(() => parseShyAgentResponse(null)).toThrow('Malformed SHY response.');
    expect(() => parseShyAgentResponse({ assistant: 'SHY' })).toThrow('Malformed SHY response status.');
  });

  it('parses health responses', () => {
    const health = parseShyHealthResponse({
      status: 'ok',
      system: 'SHY',
      version: '0.19.0',
      local_model: 'qwen3.5:4b',
      application_healthy: true,
      ollama_connected: true,
      database_connected: true,
      local_model_available: true,
    });

    expect(health.system).toBe('SHY');
    expect(health.version).toBe('0.19.0');
    expect(health.application_healthy).toBe(true);
    expect(health.ollama_connected).toBe(true);
    expect(health.local_model_available).toBe(true);
  });

  it('builds request bodies with conversation and browser time context', () => {
    expect(buildAgentRequest('Hello')).toEqual({ message: 'Hello' });
    expect(buildAgentRequest('Hello', 'conv-1')).toEqual({ message: 'Hello', conversation_id: 'conv-1' });
    expect(buildAgentRequest('What day is today?', 'conv-1', -420, 'America/Los_Angeles')).toEqual({
      message: 'What day is today?',
      conversation_id: 'conv-1',
      client_utc_offset_minutes: -420,
      client_timezone: 'America/Los_Angeles',
    });
  });

  it('formats conversation titles', () => {
    expect(formatConversationTitle('  Research   NVIDIA   Blackwell   ')).toBe('Research NVIDIA Blackwell');
  });
});