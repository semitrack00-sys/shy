'use client';

import React, { useEffect, useRef } from 'react';

interface ShyComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled?: boolean;
}

export function ShyComposer({ value, onChange, onSend, disabled }: ShyComposerProps) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    ref.current?.focus();
  }, []);

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      if (!disabled) {
        onSend();
      }
    }
  }

  return (
    <form
      className="shy-composer"
      onSubmit={(event) => {
        event.preventDefault();
        if (!disabled) {
          onSend();
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
      <div className="shy-composer-actions">
        <small>Enter sends. Shift+Enter creates a newline.</small>
        <button type="submit" className="shy-submit" disabled={disabled || value.trim().length === 0}>
          {disabled ? 'Sending…' : 'Send'}
        </button>
      </div>
    </form>
  );
}