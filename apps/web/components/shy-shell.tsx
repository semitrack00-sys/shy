'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { FRONTEND_API_BASE } from '@/lib/config';
import { buildAgentRequest, parseShyAgentResponse, parseShyHealthResponse } from '@/lib/shy-api';
import { createEmptyConversation, createInitialStore, makeAssistantMessage, makeFailureMessage, makeUserMessage, patchConversationResponse, updateConversationFromMessage, upsertConversation, loadStore, saveStore, renameConversation } from '@/lib/chat-state';
import type { ChatStore, ConversationThread, ShyHealthResponse } from '@/lib/types';
import { ShyComposer } from './shy-composer';
import { ShyMessage } from './shy-message';
import { ShySidebar } from './shy-sidebar';
import { ShyVoice } from './shy-voice';
import { ShyMemoryManager } from './shy-memory-manager';
import { ShyDocuments } from './shy-documents';
import { ShyConversationSummary } from './shy-conversation-summary';

function sortByUpdatedAt(conversations: ConversationThread[]): ConversationThread[] {
  return [...conversations].sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

function updateConversation(conversations: ConversationThread[], nextConversation: ConversationThread): ConversationThread[] {
  return sortByUpdatedAt(upsertConversation(conversations, nextConversation));
}

export function ShyShell() {
  const [store, setStore] = useState<ChatStore>(() => createInitialStore());
  const [composerValue, setComposerValue] = useState('');
  const [storageReady, setStorageReady] = useState(false);
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
    setStorageReady(true);
  }, []);

  useEffect(() => {
    if (storageReady) saveStore(window.localStorage, store);
  }, [store, storageReady]);

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
        version: 'unavailable',
        application_healthy: false,
        ollama_connected: false,
        database_connected: false,
        local_model_available: false,
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
    const conversation = createEmptyConversation(activeConversation?.projectId);
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
        body: JSON.stringify(
          buildAgentRequest(
            trimmed,
            nextConversation.conversationId,
            -new Date().getTimezoneOffset(),
            Intl.DateTimeFormat().resolvedOptions().timeZone,
            nextConversation.projectId
          )
        ),
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

        <section className="shy-content" data-settings-open={settingsOpen}>
          {settingsOpen && <section className="shy-settings" aria-label="Conversation settings">
            <form key={activeConversation?.id + activeConversation?.title} onSubmit={event => {
              event.preventDefault();
              const title = String(new FormData(event.currentTarget).get('title') ?? '');
              if (activeConversation) setStore(current => ({ ...current,
                conversations: renameConversation(current.conversations, activeConversation.id, title) }));
            }}>
              <label htmlFor="shy-conversation-title">Conversation title</label>
              <input id="shy-conversation-title" name="title" defaultValue={activeConversation?.title ?? ''} maxLength={100} required />
              <button className="shy-button" type="submit">Save title</button>
            </form>
            <p className="shy-muted">History and titles are saved in this browser. Voice permissions are session-only.</p>
            {activeConversation && <ShyConversationSummary conversation={activeConversation} />}
            <p>Memory project: <strong>{activeConversation?.projectId ?? 'default'}</strong></p>
            <form onSubmit={event => {
              event.preventDefault();
              const data = new FormData(event.currentTarget);
              const projectId = String(data.get('projectId') ?? '').trim();
              const conversation = createEmptyConversation(projectId || undefined);
              setStore(current => ({ ...current, activeConversationId: conversation.id,
                conversations: sortByUpdatedAt([conversation, ...current.conversations]) }));
              setComposerValue('');
              event.currentTarget.reset();
            }}>
              <label htmlFor="shy-new-project">New project ID</label>
              <input id="shy-new-project" name="projectId" maxLength={64} pattern="[a-z0-9][a-z0-9_.-]*" placeholder="gud-express" disabled={isSending} />
              <p className="shy-muted">Start a separate chat and memory scope. Use lowercase letters, numbers, dots, underscores or dashes. Leave blank for default. Existing chats keep their project.</p>
              <button className="shy-button" type="submit" disabled={isSending}>Start project chat</button>
            </form>
            <ShyDocuments key={`documents-${activeConversation?.projectId ?? 'default'}`} projectId={activeConversation?.projectId} />
            <ShyMemoryManager key={activeConversation?.projectId ?? 'default'} projectId={activeConversation?.projectId} />
            <button className="shy-button" type="button" onClick={() => setSettingsOpen(false)}>Close settings</button>
          </section>}
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
            <ShyVoice key={activeConversation?.id} conversationId={activeConversation?.id ?? null}
              disabled={isSending} onTranscript={text => setComposerValue(current => current.trim() ? `${current.trim()} ${text}` : text)}
              reply={activeConversation?.messages.filter(message => message.role === 'assistant').at(-1)} />
            <ShyComposer value={composerValue} onChange={setComposerValue} onSend={() => void submitMessage(composerValue)} disabled={isSending} />
          </div>
        </section>
      </main>
    </div>
  );
}
