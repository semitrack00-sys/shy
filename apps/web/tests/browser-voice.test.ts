import { afterEach, describe, expect, it, vi } from 'vitest';
import { BrowserVoice, type Recognition } from '@/lib/browser-voice';

import { FakeRecognition, fakeWindow } from './voice-fixtures';

afterEach(() => vi.useRealTimers());

describe('browser voice session', () => {
  it('requires explicit opt-in for an engine without local speech support', () => {
    class RemoteRecognition extends FakeRecognition { constructor() { super(); delete (this as Partial<Recognition>).processLocally; } }
    const { win } = fakeWindow(); win.SpeechRecognition = RemoteRecognition;
    const change = vi.fn(); const voice = new BrowserVoice(win, change);
    expect(voice.start('en-US', false, vi.fn())).toBe(false);
    expect(FakeRecognition.latest.start).not.toHaveBeenCalled();
    expect(voice.start('en-US', true, vi.fn())).toBe(true);
    voice.cancel();
  });

  it('uses local recognition by default and delivers final text exactly once', () => {
    const { win } = fakeWindow(); const transcript = vi.fn(); const voice = new BrowserVoice(win, vi.fn());
    voice.start('fr-FR', false, transcript);
    const recognition = FakeRecognition.latest;
    expect(recognition.processLocally).toBe(true);
    expect(recognition.lang).toBe('fr-FR');
    recognition.result('Bonjour'); recognition.result('Bonjour');
    expect(transcript).toHaveBeenCalledExactlyOnceWith('Bonjour');
    expect(recognition.stop).toHaveBeenCalled(); voice.cancel();
  });

  it('discards late transcripts after cancellation or a new session', () => {
    const { win } = fakeWindow(); const transcript = vi.fn(); const voice = new BrowserVoice(win, vi.fn());
    voice.start('en-US', false, transcript); const old = FakeRecognition.latest;
    voice.cancel(); old.result('should not arrive');
    voice.start('en-US', false, transcript); old.result('old session');
    FakeRecognition.latest.result('new session');
    expect(transcript).toHaveBeenCalledExactlyOnceWith('new session'); voice.cancel();
  });

  it('finishes capture on silence and enforces a deadline', () => {
    vi.useFakeTimers(); const { win } = fakeWindow(); const changed = vi.fn(); const voice = new BrowserVoice(win, changed);
    voice.start('en-US', false, vi.fn()); const first = FakeRecognition.latest;
    first.onspeechend?.(); expect(first.stop).toHaveBeenCalled();
    voice.start('en-US', false, vi.fn()); const second = FakeRecognition.latest;
    vi.advanceTimersByTime(30_000); expect(second.stop).toHaveBeenCalled();
    expect(changed.mock.lastCall?.[0].error).toContain('30-second'); voice.cancel();
  });

  it('reports denied permission without retrying or switching services', () => {
    const { win } = fakeWindow(); const changed = vi.fn(); const voice = new BrowserVoice(win, changed);
    voice.start('en-US', false, vi.fn()); FakeRecognition.latest.onerror?.({ error: 'not-allowed' });
    expect(changed.mock.lastCall?.[0].error).toContain('denied');
    expect(FakeRecognition.latest.start).toHaveBeenCalledTimes(1); voice.cancel();
  });

  it('rejects unsupported browsers and insecure contexts', () => {
    expect(new BrowserVoice({}, vi.fn()).start('en-US', true, vi.fn())).toBe(false);
    const { win } = fakeWindow(); win.isSecureContext = false;
    expect(new BrowserVoice(win, vi.fn()).start('en-US', true, vi.fn())).toBe(false);
  });

  it('keeps playback local unless remote voices were explicitly allowed', () => {
    const { win, synthesis } = fakeWindow(); const voice = new BrowserVoice(win, vi.fn());
    voice.speak('Hello', 'en-US', 1, 1, 'remote', false);
    expect(synthesis.speak.mock.lastCall?.[0].voice.voiceURI).toBe('local');
    voice.speak('Hello', 'en-US', 1, 1, 'remote', true);
    expect(synthesis.speak.mock.lastCall?.[0].voice.voiceURI).toBe('remote'); voice.cancel();
  });

  it('does not silently use a remote voice for an unsupported local language', () => {
    const { win, synthesis } = fakeWindow(); const changed = vi.fn(); const voice = new BrowserVoice(win, changed);
    voice.speak('Bonjou', 'ht-HT', 1, 1, '', false);
    expect(synthesis.speak).not.toHaveBeenCalled();
    expect(changed.mock.lastCall?.[0].error).toContain('No permitted voice');
  });

  it('stops playback before listening and ignores completion of cancelled speech', () => {
    const { win, synthesis } = fakeWindow(); const changed = vi.fn(); const voice = new BrowserVoice(win, changed);
    voice.speak('Hello', 'en-US', 1, 1, '', false); const old = synthesis.speak.mock.lastCall?.[0];
    voice.start('en-US', false, vi.fn()); old.onend();
    expect(changed.mock.lastCall?.[0]).toMatchObject({ listening: true, speaking: false }); voice.cancel();
  });
});
