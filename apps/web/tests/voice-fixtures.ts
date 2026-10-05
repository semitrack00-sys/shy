import { vi } from 'vitest';
import type { Recognition, VoiceWindow } from '@/lib/browser-voice';

export class FakeRecognition implements Recognition {
  static latest: FakeRecognition;
  lang = '';
  continuous = false;
  interimResults = false;
  processLocally = true;
  onresult: Recognition['onresult'] = null;
  onerror: Recognition['onerror'] = null;
  onend: Recognition['onend'] = null;
  onspeechend: Recognition['onspeechend'] = null;
  start = vi.fn();
  stop = vi.fn();
  abort = vi.fn();
  constructor() { FakeRecognition.latest = this; }
  result(text: string) { this.onresult?.({ results: [{ isFinal: true, 0: { transcript: text } }] }); }
}

export class FakeUtterance {
  lang = '';
  voice = null;
  rate = 1;
  volume = 1;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public text: string) {}
}

export function fakeWindow() {
  const synthesis = {
    cancel: vi.fn(), speak: vi.fn(), getVoices: vi.fn(() => [
      { voiceURI: 'local', name: 'Local English', lang: 'en-US', localService: true },
      { voiceURI: 'remote', name: 'Remote English', lang: 'en-US', localService: false },
    ]), addEventListener: vi.fn(), removeEventListener: vi.fn(),
  };
  const win = { SpeechRecognition: FakeRecognition, SpeechSynthesisUtterance: FakeUtterance, speechSynthesis: synthesis, isSecureContext: true } as unknown as VoiceWindow;
  return { win, synthesis };
}

