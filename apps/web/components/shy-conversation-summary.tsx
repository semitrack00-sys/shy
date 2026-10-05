'use client';

import React, { useMemo } from 'react';
import { summarizeConversation } from '@/lib/conversation-summary';
import type { ConversationThread } from '@/lib/types';

export function ShyConversationSummary({ conversation }: { conversation: ConversationThread }) {
  const summary = useMemo(() => summarizeConversation(conversation), [conversation]);
  return <details className="shy-conversation-summary">
    <summary>Conversation summary</summary>
    <p className="shy-muted">Extracts from the latest requests and replies. Replies are not verified facts or proof that a task completed.</p>
    {(['requests', 'replies'] as const).map(section => <section key={section}>
      <h3>{section === 'requests' ? 'Recent requests' : 'Recent replies'}</h3>
      {summary[section].length ? <ul>{summary[section].map(item => <li key={item.id}>
        <a href={`#message-${item.id}`}>{item.text}</a>
      </li>)}</ul> : <p>No {section} to summarize.</p>}
    </section>)}
    <p className="shy-muted">{summary.messagesReviewed} messages reviewed. {summary.failedReplies} failed replies.
      {' '}{summary.pendingApprovals} approval requests recorded; check the original request for its current status.</p>
    {summary.olderMessagesOmitted > 0 && <p>{summary.olderMessagesOmitted} older messages omitted from this summary.</p>}
  </details>;
}
