import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { BrowserVoice, type VoiceState } from '@/lib/browser-voice';
import { WakeSession, WAKE_SESSION_MS, parseWakePhrase } from '@/lib/wake-session';
import { FakeRecognition, FakeUtterance, fakeWindow } from './voice-fixtures';

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());
function fixture() {
  const { win, synthesis } = fakeWindow(); let session: WakeSession;
  const states: VoiceState[] = []; const draft = vi.fn(); const send = vi.fn(() => true);
  const voice = new BrowserVoice(win, state => { states.push(state); session?.observe(state); });
  session = new WakeSession(voice, vi.fn(), draft, send);
  return { voice, session, draft, send, synthesis, states };
}
it('recognizes a prefix with a word boundary and preserves accented commands', () => {
  expect(parseWakePhrase(' HEY, SHY! Bonjou ayisyen é ')).toEqual({ heard: true, command: 'Bonjou ayisyen é' });
  for (const text of ['say hey shy now', 'hey shyness', 'shy hello']) expect(parseWakePhrase(text).heard).toBe(false);
});
it('ignores unrelated speech and puts a wake command in a draft without sending', () => {
  const f = fixture(); f.session.start('review', 'en-US', false);
  FakeRecognition.latest.result('unrelated speech'); vi.advanceTimersByTime(300);
  FakeRecognition.latest.result('Hey SHY review this');
  expect(f.draft).toHaveBeenCalledExactlyOnceWith('review this'); expect(f.send).not.toHaveBeenCalled(); expect(f.session.active()).toBe(false);
});
it('allows the command in the utterance after a wake-only prefix', () => {
  const f = fixture(); f.session.start('review', 'fr-FR', false);
  FakeRecognition.latest.result('Hey SHY'); vi.advanceTimersByTime(300);
  FakeRecognition.latest.result('Bonjour'); expect(f.draft).toHaveBeenCalledExactlyOnceWith('Bonjour');
});
it('waits for the response and finishes playback before listening again', () => {
  const f = fixture(); f.session.start('handsfree', 'en-US', false);
  const recognition = FakeRecognition.latest; recognition.result('Hey SHY hello');
  vi.advanceTimersByTime(3000); expect(FakeRecognition.latest).toBe(recognition);
  f.session.setPaused(true); f.session.responseReady(); vi.advanceTimersByTime(300); expect(FakeRecognition.latest).toBe(recognition);
  f.session.setPaused(false); f.voice.speak('reply', 'en-US', 1, 1, '', false);
  vi.advanceTimersByTime(300); expect(FakeRecognition.latest).toBe(recognition);
  const utterance = f.synthesis.speak.mock.calls[0][0] as unknown as FakeUtterance;
  utterance.onend?.(); vi.advanceTimersByTime(300); expect(FakeRecognition.latest).not.toBe(recognition);
  expect(f.send).toHaveBeenCalledExactlyOnceWith('hello');
});
it('stop and provider errors discard late transcripts and pending rearming', () => {
  const f = fixture(); f.session.start('handsfree', 'en-US', false);
  const recognition = FakeRecognition.latest; f.session.stop(); recognition.result('Hey SHY late');
  vi.advanceTimersByTime(1000); expect(f.send).not.toHaveBeenCalled(); expect(FakeRecognition.latest).toBe(recognition);
  f.session.start('review', 'en-US', false); FakeRecognition.latest.onerror?.({ error: 'network' });
  expect(f.session.active()).toBe(false); vi.advanceTimersByTime(300); expect(f.draft).not.toHaveBeenCalled();
});
it('caps capture attempts, automatic messages and session duration', () => {
  const f = fixture(); f.session.start('review', 'en-US', false);
  for (let i = 0; i < 12; i++) { FakeRecognition.latest.result('unrelated'); vi.advanceTimersByTime(300); }
  expect(f.session.active()).toBe(false);
  f.session.start('handsfree', 'en-US', false);
  for (let i = 0; i < 6; i++) { FakeRecognition.latest.result('Hey SHY message'); f.session.responseReady(); vi.advanceTimersByTime(300); }
  expect(f.send).toHaveBeenCalledTimes(6); expect(f.session.active()).toBe(false);
  f.session.start('review', 'en-US', false); vi.setSystemTime(Date.now() + WAKE_SESSION_MS + 1);
  FakeRecognition.latest.result('Hey SHY too late'); expect(f.draft).not.toHaveBeenCalled(); expect(f.session.active()).toBe(false);
});
it('does not retry refused or uncertain submissions', () => {
  const f = fixture(); f.send.mockReturnValue(false); f.session.start('handsfree', 'en-US', false);
  FakeRecognition.latest.result('Hey SHY hello'); vi.advanceTimersByTime(1000);
  expect(f.session.active()).toBe(false); expect(f.send).toHaveBeenCalledTimes(1);
  f.send.mockImplementation(() => { throw new Error('uncertain'); }); f.session.start('handsfree', 'en-US', false);
  FakeRecognition.latest.result('Hey SHY hello'); expect(f.session.active()).toBe(false);
});
