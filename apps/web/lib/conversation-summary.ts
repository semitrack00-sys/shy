import type { ConversationThread } from './types';

export interface SummaryExcerpt { id: string; text: string }
export interface ConversationSummary {
  requests: SummaryExcerpt[];
  replies: SummaryExcerpt[];
  failedReplies: number;
  pendingApprovals: number;
  messagesReviewed: number;
  olderMessagesOmitted: number;
}

/** Bounded, verbatim excerpts: no generated facts or inferred completion. */
export function summarizeConversation(conversation: ConversationThread): ConversationSummary {
  const recent = conversation.messages.slice(-500);
  const excerpt = (content: string) => {
    const clean = content.replace(/```[\s\S]*?```/g, '[Code omitted]').replace(/\s+/g, ' ').trim();
    return clean.length > 220 ? clean.slice(0, 219) + '…' : clean;
  };
  const select = (role: 'user' | 'assistant') => recent
    .filter(message => message.role === role && message.content.trim() && message.status !== 'failed'
      && (role === 'user' || !message.responseStatus || ['RESPOND', 'TOOL_RESULT'].includes(message.responseStatus)))
    .slice(-3).map(message => ({ id: message.id, text: excerpt(message.content) }));
  return { requests: select('user'), replies: select('assistant'), messagesReviewed: recent.length,
    olderMessagesOmitted: conversation.messages.length - recent.length,
    failedReplies: recent.filter(message => message.role === 'assistant' && message.status === 'failed').length,
    pendingApprovals: recent.filter(message => message.responseStatus === 'AWAITING_APPROVAL').length };
}
