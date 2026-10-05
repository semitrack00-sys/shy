'use client';

import React, { useState } from 'react';
import { ShyMarkdown } from './shy-markdown';
import { ShySourceCards } from './shy-source-cards';
import { getLocalTimeLabel } from '@/lib/config';
import type { ChatMessage } from '@/lib/types';

interface ShyMessageProps {
  message: ChatMessage;
  onRetry?: (message: string) => void;
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
              <button type="button" className="shy-chip" onClick={() => onRetry(message.error ?? message.content)}>
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
        <ShyMarkdown content={message.content} />
      ) : null}

      {message.toolName === 'web.search' && message.sources?.length ? <ShySourceCards sources={message.sources} /> : null}

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
