import { describe, expect, it } from 'vitest';
import { summarizeConversation } from '@/lib/conversation-summary';
import type { ChatMessage, ConversationThread } from '@/lib/types';

const conversation = (messages: ChatMessage[]): ConversationThread => ({ id: 'chat', title: 'Test',
  createdAt: '', updatedAt: '', conversationId: null, messages });
const message = (id: string, role: 'user' | 'assistant', content: string,
  responseStatus?: ChatMessage['responseStatus'], status?: ChatMessage['status']): ChatMessage =>
  ({ id, role, content, createdAt: '', responseStatus, status });

describe('bounded conversation summaries', () => {
  it('quotes replies without treating failures or approval requests as completed answers', () => {
    const result = summarizeConversation(conversation([
      message('user', 'user', 'Write a report'), message('reply', 'assistant', 'Draft report', 'RESPOND'),
      message('approve', 'assistant', 'May I send this?', 'AWAITING_APPROVAL'),
      message('fail', 'assistant', 'Connection failed', 'FAILED', 'failed'),
    ]));
    expect(result.requests).toEqual([{ id: 'user', text: 'Write a report' }]);
    expect(result.replies).toEqual([{ id: 'reply', text: 'Draft report' }]);
    expect(result.failedReplies).toBe(1); expect(result.pendingApprovals).toBe(1);
  });

  it('bounds excerpts and makes omitted history measurable', () => {
    const result = summarizeConversation(conversation(Array.from({ length: 510 }, (_, i) =>
      message(String(i), 'user', 'a'.repeat(600)))));
    expect(result.olderMessagesOmitted).toBe(10); expect(result.messagesReviewed).toBe(500);
    expect(result.requests).toHaveLength(3); expect(result.requests[0].id).toBe('507');
    expect(result.requests.every(item => item.text.length === 220)).toBe(true);
  });

  it('omits fenced code and retains accented text', () => {
    const result = summarizeConversation(conversation([message('one', 'user', 'Bonjou\n```sh\nrm -rf /\n```\nFrançais')]));
    expect(result.requests[0].text).toBe('Bonjou [Code omitted] Français');
  });
});
