import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ShyVoice } from '@/components/shy-voice';
import type { ChatMessage } from '@/lib/types';
import { FakeRecognition, FakeUtterance, fakeWindow } from './voice-fixtures';
vi.mock('@/components/shy-local-voice', () => ({ ShyLocalVoice: () => null }));

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


it('requires session consent and defaults to wake transcript review', () => {
  const transcript = vi.fn(); const send = vi.fn(() => true);
  render(<ShyVoice conversationId="one" disabled={false} onTranscript={transcript} onHandsfreeMessage={send}/>);
  const start = screen.getByRole('button', {name:'Start wake voice session'}); expect(start).toBeDisabled();
  fireEvent.click(screen.getByLabelText('Allow a bounded wake voice session.')); fireEvent.click(start);
  act(() => FakeRecognition.latest.result('Hey SHY draft this'));
  expect(transcript).toHaveBeenCalledExactlyOnceWith('draft this'); expect(send).not.toHaveBeenCalled();
});
it('requires fresh consent after changing automatic sending and stops playback consent', () => {
  const send = vi.fn(() => true);
  render(<ShyVoice conversationId="one" disabled={false} onTranscript={vi.fn()} onHandsfreeMessage={send}/>);
  fireEvent.click(screen.getByLabelText('Allow a bounded wake voice session.'));
  fireEvent.click(screen.getByLabelText('Send wake-recognized messages automatically for this session.'));
  const start = screen.getByRole('button', {name:'Start wake voice session'}); expect(start).toBeDisabled();
  fireEvent.click(screen.getByLabelText('Allow a bounded wake voice session.')); fireEvent.click(start);
  act(() => FakeRecognition.latest.result('Hey SHY send this')); expect(send).toHaveBeenCalledExactlyOnceWith('send this');
  fireEvent.click(screen.getByRole('button', {name:'Stop voice'})); expect(start).toBeDisabled();
  expect(screen.getByLabelText('Read new replies aloud')).not.toBeChecked();
});
it('a tool approval stops capture and blocks automatic restart', () => {
  const props = {conversationId:'one',disabled:false,onTranscript:vi.fn(),onHandsfreeMessage:vi.fn(() => true)};
  const {rerender} = render(<ShyVoice {...props}/>);
  fireEvent.click(screen.getByLabelText('Send wake-recognized messages automatically for this session.'));
  fireEvent.click(screen.getByLabelText('Allow a bounded wake voice session.'));
  fireEvent.click(screen.getByRole('button', {name:'Start wake voice session'}));
  const recognition = FakeRecognition.latest;
  rerender(<ShyVoice {...props} reply={{...reply,responseStatus:'AWAITING_APPROVAL'}}/>);
  act(() => recognition.result('Hey SHY approve it'));
  expect(props.onHandsfreeMessage).not.toHaveBeenCalled(); expect(recognition.abort).toHaveBeenCalled();
  fireEvent.click(screen.getByLabelText('Allow a bounded wake voice session.'));
  expect(screen.getByRole('button', {name:'Start wake voice session'})).toBeDisabled();
});
it('pagehide cancels capture, invalidates consent and ignores late wake messages', () => {
  const send = vi.fn(() => true);
  render(<ShyVoice conversationId="one" disabled={false} onTranscript={vi.fn()} onHandsfreeMessage={send}/>);
  fireEvent.click(screen.getByLabelText('Send wake-recognized messages automatically for this session.'));
  fireEvent.click(screen.getByLabelText('Allow a bounded wake voice session.'));
  fireEvent.click(screen.getByRole('button', {name:'Start wake voice session'}));
  const recognition = FakeRecognition.latest; act(() => window.dispatchEvent(new Event('pagehide')));
  act(() => recognition.result('Hey SHY late')); expect(send).not.toHaveBeenCalled();
  expect(screen.getByRole('button', {name:'Start wake voice session'})).toBeDisabled();
});

it('shows portrait activity from real control states and clears it on stop or conversation change', () => {
  const props={conversationId:'avatar-one',disabled:false,onTranscript:vi.fn(),reply};
  const {rerender}=render(<ShyVoice {...props}/>);
  expect(screen.getByText('AI avatar')).toBeInTheDocument();
  expect(screen.getByText('Ready',{exact:true})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Speak to SHY'}));
  expect(screen.getByText('Listening',{exact:true})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button',{name:'Stop voice'}));
  expect(screen.getByText('Ready',{exact:true})).toBeInTheDocument();
  rerender(<ShyVoice {...props} disabled/>);
  expect(screen.getByText('Thinking',{exact:true})).toBeInTheDocument();
  rerender(<ShyVoice {...props}/>);
  fireEvent.click(screen.getByRole('button',{name:'Read latest reply'}));
  expect(screen.getByText('Speaking',{exact:true})).toBeInTheDocument();
  rerender(<ShyVoice {...props} conversationId="avatar-two"/>);
  expect(screen.getByText('Ready',{exact:true})).toBeInTheDocument();
});
