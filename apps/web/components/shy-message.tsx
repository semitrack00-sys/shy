'use client';

import { parseReplyPreferences, parseResearchRequest } from '@/lib/shy-api';
import { parseDocumentAnswer } from '@/lib/document-answer';

import React, { useState } from 'react';
import { ShyMarkdown } from './shy-markdown';
import { ShySourceCards } from './shy-source-cards';
import { ShyResearchContext } from './shy-research-context';
import { getLocalTimeLabel } from '@/lib/config';
import type { ChatMessage, DocumentQuestion, ResearchRequest } from '@/lib/types';

interface ShyMessageProps {
  message: ChatMessage;
  onRetry?: (message: string, documentQuestion?: DocumentQuestion, researchRequest?: ResearchRequest) => void;
}

function prettyObject(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export function ShyMessage({ message, onRetry }: ShyMessageProps) {
  const [copied, setCopied] = useState(false);
  const documentContext = parseDocumentAnswer(message.documentAnswer);
  const replyDefaults = parseReplyPreferences(message.replyPreferences);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(message.content || message.error || '');
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  }

  return (
    <article id={`message-${message.id}`} className="shy-message" data-role={message.role} data-status={message.status}>
      <div className="shy-message-header">
        <div>
          <div className="shy-message-name">{message.role === 'user' ? 'You' : 'SHY'}</div>
          <div className="shy-message-meta">
            <span>{getLocalTimeLabel(message.createdAt)}</span>
            {message.responseStatus ? <span className="shy-chip">{message.responseStatus}</span> : null}
            {message.toolName ? <span className="shy-chip">{message.toolName}</span> : null}
            {message.toolStatus ? <span className="shy-chip">{message.toolStatus}</span> : null}
          </div>
        </div>
        {message.role === 'assistant' ? (
          <div className="shy-message-actions">
            <button type="button" className="shy-chip" onClick={handleCopy}>
              {copied ? 'Copied' : 'Copy'}
            </button>
            {message.status === 'failed' && onRetry ? (
              <button type="button" className="shy-chip" onClick={() => {
                const request = parseResearchRequest(message.researchRequest);
                if (request && typeof message.researchQuery === 'string') onRetry(message.researchQuery, undefined, request);
                else onRetry(message.documentQuestion?.query ?? message.error ?? message.content, message.documentQuestion);
              }}>
                Retry
              </button>
            ) : null}
          </div>
        ) : null}
      </div>

      {message.status === 'failed' ? (
        <div className="shy-failure">
          <strong>Request failed.</strong> {message.error ?? 'SHY could not complete this request right now.'}
        </div>
      ) : message.content ? (
        message.role === 'assistant' && documentContext
          ? <pre className="shy-document-preview">{message.content}</pre>
          : <ShyMarkdown content={message.content} />
      ) : null}

      {message.role === 'assistant' && message.status !== 'failed' && documentContext?.model_invoked && <p className="shy-muted">A local model generated this reply from selected keyword excerpts. Numeric reference membership was checked; factual support and completeness were not independently verified.</p>}
      {message.role === 'assistant' && message.status !== 'failed' && replyDefaults?.applied_to_model_prompt && <p className="shy-muted">Shy supplied your reply defaults to generation. The final language and style were not verified.</p>}
      {message.role === 'assistant' && message.status !== 'failed' && replyDefaults?.status === 'unavailable' && <p className="shy-muted">Reply defaults could not be loaded for this request.</p>}
      {message.role === 'assistant' && message.status !== 'failed' && <ShyResearchContext value={message.researchAnswer} />}
      {message.role === 'assistant' && message.status !== 'failed' && Array.isArray(message.sources) && message.sources.length ? <ShySourceCards sources={message.sources} /> : null}

      {message.toolName && message.toolName !== 'web.search' && message.output ? (
        <section className="shy-tool-card" aria-label="Tool result">
          <div>
            <p className="shy-section-label">Tool result</p>
            <h4>{message.toolName}</h4>
          </div>
          <pre>{prettyObject(message.output)}</pre>
        </section>
      ) : null}
    </article>
  );
}

