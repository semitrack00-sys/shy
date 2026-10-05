export interface RecognitionResult {
  isFinal: boolean;
  0: { transcript: string };
}

export interface Recognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  processLocally?: boolean;
  onresult: ((event: { results: ArrayLike<RecognitionResult> }) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  onspeechend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export interface VoiceWindow {
  SpeechRecognition?: new () => Recognition;
  webkitSpeechRecognition?: new () => Recognition;
  speechSynthesis?: SpeechSynthesis;
  SpeechSynthesisUtterance?: new (text: string) => SpeechSynthesisUtterance;
  isSecureContext?: boolean;
}

export interface VoiceState {
  listening: boolean;
  speaking: boolean;
  error: string;
}

export const VOICE_LANGUAGES = [
  ['en-US', 'English'], ['fr-FR', 'Français'], ['ht-HT', 'Kreyòl ayisyen'],
  ['es-ES', 'Español'], ['pt-BR', 'Português'], ['ko-KR', '한국어'], ['sw-KE', 'Kiswahili'],
] as const;

const errors: Record<string, string> = {
  'not-allowed': 'Microphone permission was denied. Allow it in browser settings and try again.',
  'service-not-allowed': 'The browser speech service is unavailable.',
  'audio-capture': 'No working microphone was found. Check your system input device.',
  'no-speech': 'No speech was detected. Try again or type your message.',
  'network': 'The speech service could not connect. Your text chat is still available.',
  'language-not-supported': 'This speech engine does not support the selected language or its local language pack is missing.',
};

/** User-started, one-utterance capture. No raw audio is sent to SHY or saved. */
export class BrowserVoice {
  private recognition: Recognition | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private speechEpoch = 0;
  private state: VoiceState = { listening: false, speaking: false, error: '' };

  constructor(private win: VoiceWindow, private changed: (state: VoiceState) => void) {}

  private update(patch: Partial<VoiceState>) {
    this.state = { ...this.state, ...patch };
    this.changed(this.state);
  }

  supportsRecognition() {
    return Boolean(this.win.SpeechRecognition ?? this.win.webkitSpeechRecognition);
  }

  supportsSynthesis() {
    return Boolean(this.win.speechSynthesis && this.win.SpeechSynthesisUtterance);
  }

  start(language: string, allowBrowserService: boolean, transcript: (text: string) => void): boolean {
    this.cancel();
    const Constructor = this.win.SpeechRecognition ?? this.win.webkitSpeechRecognition;
    if (!Constructor || this.win.isSecureContext === false) {
      this.update({ error: 'Voice input requires a supported browser on HTTPS or localhost. You can still type.' });
      return false;
    }
    const recognition = new Constructor();
    if (!allowBrowserService && !('processLocally' in recognition)) {
      this.update({ error: 'On-device speech is unavailable here. Choose browser speech explicitly to use its service, or keep typing.' });
      return false;
    }
    recognition.lang = language;
    recognition.continuous = false;
    recognition.interimResults = false;
    if ('processLocally' in recognition) recognition.processLocally = !allowBrowserService;
    this.recognition = recognition;
    let delivered = false;
    recognition.onresult = (event) => {
      if (this.recognition !== recognition || delivered) return;
      const text = Array.from(event.results).filter(result => result.isFinal)
        .map(result => result[0].transcript).join(' ').trim().slice(0, 8000);
      if (text) {
        delivered = true;
        transcript(text);
        this.stopListening();
      }
    };
    recognition.onerror = (event) => {
      if (this.recognition !== recognition) return;
      if (event.error !== 'aborted') this.update({ error: errors[event.error] ?? 'Speech recognition failed. Try again or type your message.' });
      this.cancel();
    };
    recognition.onend = () => {
      if (this.recognition !== recognition) return;
      this.clearTimer();
      this.recognition = null;
      this.update({ listening: false });
    };
    recognition.onspeechend = () => {
      if (this.recognition === recognition) this.stopListening();
    };
    try {
      recognition.start();
      this.update({ listening: true, error: '' });
      this.timer = setTimeout(() => {
        if (this.recognition === recognition) {
          this.update({ error: 'Recording reached the 30-second limit. Review your transcript or try again.' });
          this.stopListening();
        }
      }, 30_000);
      return true;
    } catch {
      this.cancel();
      this.update({ error: 'The microphone could not start. Check permission and try again.' });
      return false;
    }
  }

  private clearTimer() {
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
  }

  stopListening() {
    this.clearTimer();
    try { this.recognition?.stop(); } catch { /* Browser may already have stopped. */ }
    this.update({ listening: false });
  }

  stopSpeaking() {
    this.speechEpoch += 1;
    this.win.speechSynthesis?.cancel();
    this.update({ speaking: false });
  }

  speak(text: string, language: string, rate: number, volume: number, voiceURI: string, allowBrowserService: boolean) {
    this.cancel();
    const synthesis = this.win.speechSynthesis;
    const Utterance = this.win.SpeechSynthesisUtterance;
    if (!synthesis || !Utterance) return this.update({ error: 'Spoken replies are unavailable in this browser.' });
    const voices = synthesis.getVoices().filter(voice => allowBrowserService || voice.localService);
    const voice = voices.find(item => item.voiceURI === voiceURI)
      ?? voices.find(item => item.lang.toLowerCase() === language.toLowerCase())
      ?? voices.find(item => item.lang.split('-')[0] === language.split('-')[0]);
    if (!voice) return this.update({ error: 'No permitted voice matches this language. Install a system voice or choose browser speech explicitly.' });
    const utterance = new Utterance(text.replace(/```[\s\S]*?```/g, ' Code omitted. ').replace(/https?:\/\/\S+/g, 'link').slice(0, 4000));
    utterance.lang = language;
    utterance.voice = voice;
    utterance.rate = Math.min(1.5, Math.max(0.5, rate));
    utterance.volume = Math.min(1, Math.max(0, volume));
    const epoch = this.speechEpoch;
    utterance.onend = () => { if (this.speechEpoch === epoch) this.update({ speaking: false }); };
    utterance.onerror = () => { if (this.speechEpoch === epoch) this.update({ speaking: false, error: 'Playback failed. Your written reply is still available.' }); };
    this.update({ speaking: true, error: '' });
    try { synthesis.speak(utterance); } catch { this.update({ speaking: false, error: 'Playback could not start.' }); }
  }

  cancel() {
    const recognition = this.recognition;
    this.recognition = null; // Discard events from cancelled sessions, including late transcripts.
    this.clearTimer();
    try { recognition?.abort(); } catch { /* Already closed. */ }
    this.stopSpeaking();
    this.update({ listening: false });
  }
}
