'use client';

import React, { useState } from 'react';
import { searchConversations } from '@/lib/chat-state';
import type { ConversationThread } from '@/lib/types';
import { ShyStatus } from './shy-status';

interface ShySidebarProps {
  conversations: ConversationThread[];
  activeConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onNewChat: () => void;
  onOpenSettings: () => void;
  onClose?: () => void;
  open: boolean;
  onRefreshHealth: () => void;
  health: Parameters<typeof ShyStatus>[0]['health'];
  loadingHealth: boolean;
}

export function ShySidebar({
  conversations,
  activeConversationId,
  onSelectConversation,
  onNewChat,
  onOpenSettings,
  onClose,
  open,
  onRefreshHealth,
  health,
  loadingHealth,
}: ShySidebarProps) {
  const [query, setQuery] = useState('');
  const visible = searchConversations(conversations, query);
  return (
    <aside className="shy-sidebar" data-open={open} aria-label="Conversation sidebar">
      <div className="shy-brand">
        <div className="shy-mark" aria-hidden="true" />
        <div>
          <h1>SHY</h1>
          <p>Professional assistant workspace</p>
        </div>
      </div>

      <div className="shy-sidebar-section">
        <button type="button" className="shy-button" onClick={onNewChat}>
          New chat
        </button>
        <button type="button" className="shy-button" onClick={onOpenSettings}>
          Settings
        </button>
        <button type="button" className="shy-button" onClick={onRefreshHealth}>
          Refresh status
        </button>
        {onClose ? (
          <button type="button" className="shy-button shy-mobile-toggle" onClick={onClose}>
            Close sidebar
          </button>
        ) : null}
      </div>

      <section className="shy-sidebar-section">
        <div>
          <p className="shy-section-label">Conversations</p>
          <h2>History</h2>
        </div>
        <div className="shy-thread-list">
          <label htmlFor="shy-history-search">Search conversations</label>
          <input id="shy-history-search" type="search" value={query} maxLength={200}
            onChange={event => setQuery(event.target.value)} placeholder="Search titles and messages" />
          {visible.length === 0 && <p className="shy-muted">No matching conversations.</p>}
          {visible.map((conversation) => (
            <button
              key={conversation.id}
              type="button"
              className="shy-thread-button"
              aria-current={conversation.id === activeConversationId}
              onClick={() => onSelectConversation(conversation.id)}
            >
              <strong>{conversation.title}</strong>
              <div className="shy-muted">{conversation.messages.length} messages</div>
            </button>
          ))}
        </div>
      </section>

      <ShyStatus health={health} loading={loadingHealth} />
    </aside>
  );
}
