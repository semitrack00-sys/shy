import { BrowserVoice, type VoiceState } from './browser-voice';

export type WakeMode = 'review' | 'handsfree';
export type WakeState = { active: boolean; awaitingCommand: boolean; mode: WakeMode; notice: string };
export const WAKE_SESSION_MS = 180_000;
export const MAX_WAKE_CAPTURES = 12;
export const MAX_WAKE_MESSAGES = 6;

export function parseWakePhrase(text: string): { heard: boolean; command: string } {
  const match = /^hey[\s,]+shy(?=$|[\s,.!?:;-])[\s,.!?:;-]*([\s\S]*)$/i.exec(text.normalize('NFKC').trim());
  return match ? { heard: true, command: match[1].trim().slice(0, 8000) } : { heard: false, command: '' };
}

/** User-started transcript prefix recognition, not an acoustic wake model. */
export class WakeSession {
  private current: WakeState = { active: false, awaitingCommand: false, mode: 'review', notice: '' };
  private voiceState: VoiceState = { listening: false, speaking: false, error: '' };
  private expiry: ReturnType<typeof setTimeout> | null = null;
  private retry: ReturnType<typeof setTimeout> | null = null;
  private epoch = 0;
  private captures = 0;
  private sent = 0;
  private paused = false;
  private waiting = false;
  private starting = false;
  private deadline = 0;
  private language = 'en-US';
  private allowBrowserService = false;
  constructor(private voice: BrowserVoice, private changed: (state: WakeState) => void,
    private draft: (text: string) => void, private send: (text: string) => boolean) {}

  private update(patch: Partial<WakeState>) { this.current = { ...this.current, ...patch }; this.changed(this.current); }
  active() { return this.current.active; }
  start(mode: WakeMode, language: string, allowBrowserService: boolean) {
    this.stop(); this.epoch++; this.captures = 0; this.sent = 0; this.waiting = false; this.paused = false;
    this.language = language; this.allowBrowserService = allowBrowserService;
    this.deadline = Date.now() + WAKE_SESSION_MS;
    this.update({ active: true, awaitingCommand: false, mode, notice: 'Say “Hey SHY” and your message.' });
    const epoch = this.epoch;
    this.expiry = setTimeout(() => { if (epoch === this.epoch) this.stop('Voice session reached its three-minute limit.'); }, WAKE_SESSION_MS);
    this.capture(); return this.current.active;
  }
  observe(state: VoiceState) {
    this.voiceState = state;
    if (!this.current.active || this.starting) return;
    if (state.error) return this.stop('Voice session stopped after a speech or playback error.');
    if (state.listening || state.speaking) { this.clearRetry(); return; }
    this.schedule();
  }
  private clearRetry() { if (this.retry) clearTimeout(this.retry); this.retry = null; }
  setPaused(paused: boolean) { this.paused = paused; if (paused) this.clearRetry(); else this.schedule(); }
  responseReady() { this.waiting = false; this.schedule(); }
  private schedule() {
    if (!this.current.active || this.paused || this.waiting || this.voiceState.listening || this.voiceState.speaking || this.retry) return;
    const epoch = this.epoch;
    this.retry = setTimeout(() => { this.retry = null; if (epoch === this.epoch) this.capture(); }, 300);
  }
  private capture() {
    if (!this.current.active || this.paused || this.waiting || this.voiceState.speaking) return;
    if (Date.now() >= this.deadline) return this.stop('Voice session reached its three-minute limit.');
    if (this.captures >= MAX_WAKE_CAPTURES) return this.stop('Voice session reached its twelve-capture limit.');
    this.captures++; this.starting = true;
    const epoch = this.epoch;
    const started = this.voice.start(this.language, this.allowBrowserService, text => {
      if (epoch !== this.epoch || !this.current.active || this.paused || this.waiting) return;
      if (Date.now() >= this.deadline) return this.stop('Voice session reached its three-minute limit.');
      let command = text.trim();
      if (!this.current.awaitingCommand) {
        const parsed = parseWakePhrase(command);
        if (!parsed.heard) { this.update({ notice: 'Wake phrase not heard. Waiting for “Hey SHY”…' }); return; }
        command = parsed.command;
        if (!command) { this.update({ awaitingCommand: true, notice: 'Wake phrase heard. Say your message.' }); return; }
      }
      this.update({ awaitingCommand: false });
      if (this.current.mode === 'review') {
        this.stop('Transcript added to your draft. Review it before sending.'); this.draft(command); return;
      }
      this.waiting = true;
      let accepted = false;
      try { accepted = this.send(command); } catch { /* Stop without retrying an uncertain submission. */ }
      if (!accepted) return this.stop('Message was not sent. Review your draft or try again.');
      this.sent++;
      if (this.sent >= MAX_WAKE_MESSAGES) return this.stop('Voice session reached its six-message limit.');
      this.update({ notice: 'Message sent. Waiting for SHY before listening again.' });
    });
    this.starting = false;
    if (!started) this.stop('Voice session could not start. Check the speech error and permission.');
  }
  stop(notice = 'Voice session stopped.') {
    const wasActive = this.current.active;
    this.epoch++; this.current = { ...this.current, active: false, awaitingCommand: false, notice };
    if (this.expiry) clearTimeout(this.expiry);
    this.expiry = null; this.clearRetry(); this.waiting = false;
    if (wasActive) this.voice.cancel();
    this.changed(this.current);
  }
}
