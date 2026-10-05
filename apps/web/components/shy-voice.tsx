'use client';

import React, { useEffect, useRef, useState } from 'react';
import { BrowserVoice, VOICE_LANGUAGES, type VoiceState, type VoiceWindow } from '@/lib/browser-voice';
import type { ChatMessage } from '@/lib/types';
import { ShyLocalVoice } from './shy-local-voice';

export function ShyVoice({ conversationId, disabled, onTranscript, reply }: {
  conversationId: string | null;
  disabled: boolean;
  onTranscript: (text: string) => void;
  reply?: ChatMessage;
}) {
  const controller = useRef<BrowserVoice | null>(null);
  const [state, setState] = useState<VoiceState>({ listening: false, speaking: false, error: '' });
  const [supported, setSupported] = useState(false);
  const [synthesisSupported, setSynthesisSupported] = useState(false);
  const [allowBrowserService, setAllowBrowserService] = useState(false);
  const [readReplies, setReadReplies] = useState(false);
  const [language, setLanguage] = useState('en-US');
  const [rate, setRate] = useState(1);
  const [volume, setVolume] = useState(1);
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voiceURI, setVoiceURI] = useState('');
  const [localActive, setLocalActive] = useState(false);
  const [cancelSignal, setCancelSignal] = useState(0);
  const lastReply = useRef(reply?.id);

  useEffect(() => {
    const voice = new BrowserVoice(window as unknown as VoiceWindow, setState);
    controller.current = voice;
    setSupported(voice.supportsRecognition());
    setSynthesisSupported(voice.supportsSynthesis());
    const refresh = () => setVoices(window.speechSynthesis?.getVoices() ?? []);
    refresh();
    window.speechSynthesis?.addEventListener('voiceschanged', refresh);
    return () => {
      window.speechSynthesis?.removeEventListener('voiceschanged', refresh);
      voice.cancel();
      controller.current = null;
    };
  }, []);

  useEffect(() => {
    controller.current?.cancel();
    lastReply.current = reply?.id;
    // A conversation change invalidates recording and queued playback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  useEffect(() => {
    if (disabled) controller.current?.cancel();
  }, [disabled]);

  useEffect(() => {
    if (disabled || localActive) return;
    if (reply?.id === lastReply.current) return;
    lastReply.current = reply?.id;
    if (readReplies && reply && reply.status !== 'failed') {
      controller.current?.speak(reply.content, language, rate, volume, voiceURI, allowBrowserService);
    }
  }, [reply, disabled, localActive, readReplies, language, rate, volume, voiceURI, allowBrowserService]);

  useEffect(() => {
    const stop = () => { if (document.hidden) controller.current?.cancel(); };
    document.addEventListener('visibilitychange', stop);
    return () => document.removeEventListener('visibilitychange', stop);
  }, []);

  return (
    <section className="shy-voice" aria-label="Voice conversation">
      <div className="shy-voice-actions">
        <button className="shy-button" type="button" disabled={disabled || localActive || !supported}
          aria-pressed={state.listening} onClick={() => state.listening
            ? controller.current?.stopListening()
            : controller.current?.start(language, allowBrowserService, onTranscript)}>
          {state.listening ? 'Finish recording' : 'Speak to SHY'}
        </button>
        <button className="shy-button" type="button" disabled={!state.listening && !state.speaking && !localActive}
          onClick={() => { controller.current?.cancel(); setCancelSignal(value => value + 1); }}>Stop voice</button>
        <button className="shy-button" type="button" disabled={!reply || disabled || localActive || !synthesisSupported}
          onClick={() => reply && controller.current?.speak(reply.content, language, rate, volume, voiceURI, allowBrowserService)}>
          Read latest reply
        </button>
      </div>
      <p className="shy-muted" role="status">{state.listening ? 'Listening… finish when ready.'
        : state.speaking ? 'SHY is speaking…' : 'Speak, review the transcript, then press Send.'}</p>
      {!supported && <p className="shy-muted">Voice input is unavailable in this browser. Text chat remains available.</p>}
      {state.error && <p role="alert">{state.error}</p>}
      <details>
        <summary>Voice settings and privacy</summary>
        <p>On-device speech is used when supported. Browser speech may send audio or text to your browser’s speech provider. SHY receives the transcript only when you send it. Audio is not saved by SHY.</p>
        <label><input type="checkbox" checked={allowBrowserService} onChange={event => {
          controller.current?.cancel(); setAllowBrowserService(event.target.checked);
        }} /> Allow browser speech services for this session</label>
        <label><input type="checkbox" checked={readReplies} disabled={!synthesisSupported} onChange={event => {
          controller.current?.stopSpeaking(); setReadReplies(event.target.checked);
        }} /> Read new replies aloud</label>
        <label>Language<select value={language} onChange={event => {
          controller.current?.cancel(); setLanguage(event.target.value); setVoiceURI('');
        }}>{VOICE_LANGUAGES.map(([code, label]) => <option key={code} value={code}>{label}</option>)}</select></label>
        <small>Recognition and installed voices determine language availability. Haitian Creole support is not guaranteed.</small>
        <label>Voice<select value={voiceURI} onChange={event => { controller.current?.stopSpeaking(); setVoiceURI(event.target.value); }}>
          <option value="">Match selected language</option>
          {voices.filter(voice => allowBrowserService || voice.localService).map(voice =>
            <option key={voice.voiceURI} value={voice.voiceURI}>{voice.name} ({voice.lang})</option>)}
        </select></label>
        <label>Speaking speed<input type="range" min="0.5" max="1.5" step="0.1" value={rate}
          onChange={event => setRate(Number(event.target.value))} /></label>
        <label>Volume<input type="range" min="0" max="1" step="0.1" value={volume}
          onChange={event => setVolume(Number(event.target.value))} /></label>
      </details>
      <ShyLocalVoice disabled={disabled} onTranscript={onTranscript} onStart={() => controller.current?.cancel()}
        onActivity={setLocalActive} cancelSignal={cancelSignal} />
    </section>
  );
}
