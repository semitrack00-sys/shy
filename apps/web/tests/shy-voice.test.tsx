import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ShyVoice } from '@/components/shy-voice';
import type { ChatMessage } from '@/lib/types';
import { FakeRecognition, FakeUtterance, fakeWindow } from './voice-fixtures';

let synthesis: ReturnType<typeof fakeWindow>['synthesis'];
beforeEach(() => {
  synthesis = fakeWindow().synthesis;
  Object.defineProperty(window, 'SpeechRecognition', { configurable: true, value: FakeRecognition });
  Object.defineProperty(window, 'SpeechSynthesisUtterance', { configurable: true, value: FakeUtterance });
  Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: synthesis });
});
afterEach(() => cleanup());
const reply: ChatMessage = { id: 'reply-1', role: 'assistant', content: 'Hello', createdAt: '', status: 'sent' };

describe('voice controls', () => {
  it('puts recognized speech in the draft for review and never submits it automatically', () => {
    const transcript = vi.fn(); render(<ShyVoice conversationId="one" disabled={false} onTranscript={transcript} />);
    fireEvent.click(screen.getByRole('button', { name: 'Speak to SHY' }));
    act(() => FakeRecognition.latest.result('hello SHY'));
    expect(transcript).toHaveBeenCalledExactlyOnceWith('hello SHY');
    expect(screen.getByText(/review the transcript/i)).toBeInTheDocument();
  });

  it('does not read historical replies when the user enables spoken replies', () => {
    render(<ShyVoice conversationId="one" disabled={false} onTranscript={vi.fn()} reply={reply} />);
    fireEvent.click(screen.getByLabelText('Read new replies aloud'));
    expect(synthesis.speak).not.toHaveBeenCalled();
  });

  it('reads a new reply after sending finishes and permits interruption', () => {
    const props = { conversationId: 'one', disabled: false, onTranscript: vi.fn() };
    const { rerender } = render(<ShyVoice {...props} />);
    fireEvent.click(screen.getByLabelText('Read new replies aloud'));
    rerender(<ShyVoice {...props} disabled reply={reply} />);
    expect(synthesis.speak).not.toHaveBeenCalled();
    rerender(<ShyVoice {...props} reply={reply} />);
    expect(synthesis.speak).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Stop voice' }));
    expect(screen.getByRole('button', { name: 'Stop voice' })).toBeDisabled();
  });

  it('cancels recording when switching conversations and ignores late transcripts', () => {
    const transcript = vi.fn(); const props = { disabled: false, onTranscript: transcript };
    const { rerender } = render(<ShyVoice {...props} conversationId="one" />);
    fireEvent.click(screen.getByRole('button', { name: 'Speak to SHY' })); const recognition = FakeRecognition.latest;
    rerender(<ShyVoice {...props} conversationId="two" />);
    act(() => recognition.result('wrong conversation'));
    expect(transcript).not.toHaveBeenCalled(); expect(recognition.abort).toHaveBeenCalled();
  });

  it('cancels recording when the component is removed', () => {
    const { unmount } = render(<ShyVoice conversationId="one" disabled={false} onTranscript={vi.fn()} />);
    fireEvent.click(screen.getByRole('button', { name: 'Speak to SHY' })); const recognition = FakeRecognition.latest;
    unmount(); expect(recognition.abort).toHaveBeenCalled();
  });
});
