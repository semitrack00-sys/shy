'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { FRONTEND_API_BASE } from '@/lib/config';
import { buildAgentRequest, parseShyAgentResponse, parseShyHealthResponse } from '@/lib/shy-api';
import { createEmptyConversation, createInitialStore, makeAssistantMessage, makeFailureMessage, makeUserMessage, patchConversationResponse, updateConversationFromMessage, upsertConversation, loadStore, saveStore } from '@/lib/chat-state';
import type { ChatStore, ConversationThread, ShyHealthResponse } from '@/lib/types';
import { ShyComposer } from './shy-composer';
import { ShyMessage } from './shy-message';
import { ShySidebar } from './shy-sidebar';

function sortByUpdatedAt(conversations: ConversationThread[]): ConversationThread[] {
  return [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

function updateConversation(conversations: ConversationThread[], nextConversation: ConversationThread): ConversationThread[] {
  return sortByUpdatedAt(upsertConversation(conversations, nextConversation));
}

export function ShyShell() {
  const [store, setStore] = useState<ChatStore>(() => createInitialStore());
  const [composerValue, setComposerValue] = useState('');
  const [isSending, setIsSending] = useState(false);
  const [health, setHealth] = useState<ShyHealthResponse | null>(null);
  const [healthLoading, setHealthLoading] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  const activeConversation = useMemo(
    () => store.conversations.find((conversation) => conversation.id === store.activeConversationId) ?? store.conversations[0],
    [store.conversations, store.activeConversationId]
  );

  useEffect(() => {
    const persisted = loadStore(window.localStorage);
    setStore((current) => {
      if (current.conversations.length > 0 && current.conversations[0].messages.length > 0) {
        return current;
      }
      return persisted;
    });
  }, []);

  useEffect(() => {
    saveStore(window.localStorage, store);
  }, [store]);

  useEffect(() => {
    document.documentElement.dataset.theme = store.theme;
  }, [store.theme]);

  useEffect(() => {
    void refreshHealth();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [activeConversation?.messages.length, isSending]);

  async function refreshHealth() {
    setHealthLoading(true);
    try {
      const response = await fetch(`${FRONTEND_API_BASE}/health`, { cache: 'no-store' });
      const payload = parseShyHealthResponse(await response.json());
      setHealth(payload);
    } catch {
      setHealth({
        status: 'error',
        system: 'SHY',
        version: '0.9.0',
        ollama_connected: false,
        database_connected: false,
      });
    } finally {
      setHealthLoading(false);
    }
  }

  function setActiveConversation(id: string) {
    setStore((current) => ({ ...current, activeConversationId: id }));
    setSidebarOpen(false);
  }

  function createNewChat() {
    const conversation = createEmptyConversation();
    setStore((current) => ({
      ...current,
      activeConversationId: conversation.id,
      conversations: sortByUpdatedAt([conversation, ...current.conversations]),
    }));
    setComposerValue('');
    setSidebarOpen(false);
  }

  function toggleTheme() {
    setStore((current) => ({
      ...current,
      theme: current.theme === 'dark' ? 'light' : 'dark',
    }));
  }

  function updateConversationState(nextConversation: ConversationThread) {
    setStore((current) => ({
      ...current,
      conversations: updateConversation(current.conversations, nextConversation),
      activeConversationId: nextConversation.id,
    }));
  }

  async function submitMessage(messageText: string) {
    const trimmed = messageText.trim();
    if (!trimmed || isSending) return;

    let conversation = activeConversation ?? createEmptyConversation();
    if (!store.activeConversationId) {
      setStore((current) => ({ ...current, activeConversationId: conversation.id, conversations: sortByUpdatedAt([conversation, ...current.conversations]) }));
    }

    const userMessage = makeUserMessage(trimmed);
    const nextConversation = updateConversationFromMessage(conversation, userMessage);
    updateConversationState(nextConversation);
    setComposerValue('');
    setIsSending(true);

    try {
      const response = await fetch(`${FRONTEND_API_BASE}/agent`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(buildAgentRequest(trimmed, nextConversation.conversationId)),
      });

      const parsed = parseShyAgentResponse(await response.json());
      const assistantMessage = parsed.status === 'FAILED'
        ? makeFailureMessage(parsed.reason ?? 'SHY could not complete that request right now.')
        : makeAssistantMessage(parsed);

      const updatedConversation = patchConversationResponse(nextConversation, parsed, assistantMessage);

      setStore((current) => ({
        ...current,
        conversations: updateConversation(current.conversations, updatedConversation),
        activeConversationId: updatedConversation.id,
      }));
    } catch (error) {
      const failureMessage = makeFailureMessage(error instanceof Error ? error.message : 'Unable to reach SHY right now.');
      const failedConversation: ConversationThread = {
        ...nextConversation,
        updatedAt: failureMessage.createdAt,
        messages: [...nextConversation.messages, failureMessage],
      };
      updateConversationState(failedConversation);
    } finally {
      setIsSending(false);
    }
  }

  function retryMessage(message: string) {
    void submitMessage(message);
  }

  return (
    <div className="shy-app-shell">
      {sidebarOpen ? <button type="button" className="shy-drawer-backdrop" aria-label="Close sidebar" onClick={() => setSidebarOpen(false)} /> : null}

      <ShySidebar
        conversations={store.conversations}
        activeConversationId={store.activeConversationId}
        onSelectConversation={setActiveConversation}
        onNewChat={createNewChat}
        onOpenSettings={() => setSettingsOpen((current) => !current)}
        onClose={() => setSidebarOpen(false)}
        open={sidebarOpen}
        onRefreshHealth={() => void refreshHealth()}
        health={health}
        loadingHealth={healthLoading}
      />

      <main className="shy-main">
        <header className="shy-topbar">
          <div className="shy-brand">
            <button type="button" className="shy-icon-button shy-mobile-toggle" onClick={() => setSidebarOpen(true)} aria-label="Open sidebar">
              ☰
            </button>
            <div className="shy-mark" aria-hidden="true" />
            <div>
              <h1>SHY</h1>
              <p>Professional AI assistant workspace</p>
            </div>
          </div>

          <div className="shy-header-actions">
            <span className="shy-chip">{health?.system ?? 'SHY'}</span>
            <button type="button" className="shy-button" onClick={toggleTheme}>
              {store.theme === 'dark' ? 'Light mode' : 'Dark mode'}
            </button>
          </div>
        </header>

        <section className="shy-content">
          {activeConversation && activeConversation.messages.length > 0 ? (
            <div className="shy-messages" aria-live="polite">
              {activeConversation.messages.map((message) => (
                <ShyMessage key={message.id} message={message} onRetry={retryMessage} />
              ))}
              <div ref={messagesEndRef} />
            </div>
          ) : (
            <div className="shy-empty-state">
              <h2 className="shy-empty-title">SHY</h2>
              <p className="shy-muted">How can I help you?</p>
            </div>
          )}

          <div className="shy-composer-shell">
            <ShyComposer value={composerValue} onChange={setComposerValue} onSend={() => void submitMessage(composerValue)} disabled={isSending} />
          </div>
        </section>
      </main>
    </div>
  );
}