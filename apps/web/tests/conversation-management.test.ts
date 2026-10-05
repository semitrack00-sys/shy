import { describe, expect, it } from 'vitest';
import { createEmptyConversation, renameConversation, searchConversations } from '@/lib/chat-state';

describe('conversation management', () => {
  it('searches titles and message contents without changing history', () => {
    const one = { ...createEmptyConversation(), id: 'one', title: 'Trucking', messages: [{ id: 'm', role: 'user' as const, content: 'Bonjou fanmi', createdAt: '' }] };
    const two = { ...createEmptyConversation(), id: 'two', title: 'Solar kit' };
    const history = [one, two];
    expect(searchConversations(history, ' FANMI ')).toEqual([one]);
    expect(searchConversations(history, 'solar')).toEqual([two]);
    expect(searchConversations(history, 'unknown')).toEqual([]);
    expect(searchConversations(history, '')).toBe(history);
  });

  it('renames only the selected conversation while preserving content and backend identity', () => {
    const one = { ...createEmptyConversation(), id: 'one', conversationId: 'backend' };
    const two = { ...createEmptyConversation(), id: 'two' };
    const renamed = renameConversation([one, two], 'one', '  My project  ');
    expect(renamed[0]).toMatchObject({ title: 'My project', conversationId: 'backend', messages: [] });
    expect(renamed[1]).toBe(two); expect(one.title).toBe('New chat');
    expect(renameConversation(renamed, 'one', '   ')).toBe(renamed);
    expect(renameConversation(renamed, 'one', 'a'.repeat(150))[0].title).toHaveLength(100);
  });
});
