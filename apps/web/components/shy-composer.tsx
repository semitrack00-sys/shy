'use client';

import React, { useEffect, useRef, useState } from 'react';

interface ShyComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (research?: boolean) => void;
  researchAvailable?: boolean;
  disabled?: boolean;
}

export function ShyComposer({ value, onChange, onSend, disabled, researchAvailable }: ShyComposerProps) {
  const [searchWeb, setSearchWeb] = useState(false);
  const suggested = /\b(today|latest|current|news|weather|price|prices|recent|this week|aujourd’hui|aujourd'hui|actualité|jodi a|hoy|noticias)\b/i.test(value);
  const tooLong = searchWeb && value.trim().length > 1000;
  function send() {
    if (disabled || tooLong || !value.trim()) return;
    onSend(searchWeb && researchAvailable === true);
    setSearchWeb(false);
  }
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    ref.current?.focus({ preventScroll: true });
  }, []);

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!disabled) {
        send();
      }
    }
  }

  return (
    <form
      className="shy-composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (!disabled) {
          send();
        }
      }}
    >
      <label className="sr-only" htmlFor="shy-composer-input">
        Message SHY
      </label>
      <textarea
        ref={ref}
        id="shy-composer-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="How can I help you?"
        disabled={disabled}
      />
      <div>
        {suggested && !searchWeb && <p className="shy-muted">This may need up-to-date sources. {researchAvailable ? 'Select Search web for this answer to check public sources.' : 'Web research is not configured. SHY cannot verify current facts yet.'}</p>}
        <label><input type="checkbox" checked={searchWeb} disabled={disabled || !researchAvailable} onChange={event => setSearchWeb(event.target.checked)} /> Search web for this answer</label>
        {searchWeb && <p className="shy-muted">Sends this message to the public search provider. Include the topic in your question; saved memories and earlier chat messages are not used as search queries. Source dates are estimates, and citations do not guarantee accuracy.</p>}
        {tooLong && <p role="alert">Shorten your web research question to 1,000 characters or fewer.</p>}
      </div>
      <div className="shy-composer-actions">
        <small>Enter sends. Shift+Enter creates a newline.</small>
        <button type="submit" className="shy-submit" disabled={disabled || tooLong || value.trim().length === 0}>
          {disabled ? 'Sending…' : searchWeb ? 'Search and answer' : 'Send'}
        </button>
      </div>
    </form>
  );
}