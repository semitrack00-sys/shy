'use client';

import React, { useEffect, useRef, useState } from 'react';
import { BrowserVoice, VOICE_LANGUAGES, type VoiceState, type VoiceWindow } from '@/lib/browser-voice';
import { WakeSession, type WakeState } from '@/lib/wake-session';
import type { ChatMessage } from '@/lib/types';
import { ShyAvatar, type AvatarState } from './shy-avatar';
import { ShyLocalVoice } from './shy-local-voice';

export function ShyVoice({ conversationId, disabled, onTranscript, onHandsfreeMessage, reply }: {
  conversationId: string | null;
  disabled: boolean;
  onTranscript: (text: string) => void;
  onHandsfreeMessage?: (text: string) => boolean;
  reply?: ChatMessage;
}) {
  const controller = useRef<BrowserVoice | null>(null);
  const session = useRef<WakeSession | null>(null);
  const transcriptRef = useRef(onTranscript); transcriptRef.current = onTranscript;
  const sendRef = useRef(onHandsfreeMessage); sendRef.current = onHandsfreeMessage;
  const [sessionState, setSessionState] = useState<WakeState>({active:false, awaitingCommand:false, mode:'review', notice:''});
  const [sessionConsent, setSessionConsent] = useState(false);
  const [handsfree, setHandsfree] = useState(false);
  const blockedReply = reply?.status === 'failed' || ['AWAITING_APPROVAL','INVALID_APPROVAL','DENIED','BLOCKED','UNAVAILABLE'].includes(reply?.responseStatus ?? '');
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
  const [localVoiceState, setLocalVoiceState] = useState<'idle' | 'listening' | 'transcribing'>('idle');
  const [cancelSignal, setCancelSignal] = useState(0);
  const lastReply = useRef(reply?.id);

  useEffect(() => {
    const voice = new BrowserVoice(window as unknown as VoiceWindow, next => { setState(next); session.current?.observe(next); });
    controller.current = voice;
    session.current = new WakeSession(voice, next => {
      setSessionState(next);
      if (!next.active && next.mode === 'handsfree') setReadReplies(false);
    }, text => transcriptRef.current(text), text => sendRef.current?.(text) ?? false);
    setSupported(voice.supportsRecognition());
    setSynthesisSupported(voice.supportsSynthesis());
    const refresh = () => setVoices(window.speechSynthesis?.getVoices() ?? []);
    refresh();
    window.speechSynthesis?.addEventListener('voiceschanged', refresh);
    return () => {
      window.speechSynthesis?.removeEventListener('voiceschanged', refresh);
      session.current?.stop(); session.current = null;
      voice.cancel();
      controller.current = null;
    };
  }, []);

  useEffect(() => {
    session.current?.stop(); setSessionConsent(false); setHandsfree(false);
    controller.current?.cancel();
    setCancelSignal(value => value + 1);
    lastReply.current = reply?.id;
    // A conversation change invalidates recording and queued playback.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  useEffect(() => {
    session.current?.setPaused(disabled || localActive);
    if (disabled) controller.current?.cancel();
  }, [disabled, localActive]);

  useEffect(() => {
    if (disabled || localActive) return;
    if (reply?.id === lastReply.current) return;
    lastReply.current = reply?.id;
    if (blockedReply) {
      session.current?.stop('Voice session stopped. Review the response or approval in text.');
      if (sessionState.mode === 'handsfree') return;
    }
    session.current?.responseReady();
    if (readReplies && reply && reply.status !== 'failed') {
      controller.current?.speak(reply.content, language, rate, volume, voiceURI, allowBrowserService);
    }
  }, [reply, disabled, localActive, readReplies, language, rate, volume, voiceURI, allowBrowserService, blockedReply, sessionState.mode]);

  useEffect(() => {
    const stopSession = () => { session.current?.stop(); setSessionConsent(false); controller.current?.cancel(); };
    const stop = () => { if (document.hidden) stopSession(); };
    document.addEventListener('visibilitychange', stop);
    window.addEventListener('pagehide', stopSession);
    return () => { document.removeEventListener('visibilitychange', stop); window.removeEventListener('pagehide', stopSession); };
  }, []);

  const avatarState: AvatarState = disabled ? 'thinking' : state.speaking ? 'speaking' : state.listening || localVoiceState === 'listening' ? 'listening' : localVoiceState === 'transcribing' ? 'transcribing' : state.error ? 'unavailable' : 'idle';

  return (
    <section className="shy-voice" aria-label="Voice conversation">
      <ShyAvatar size="voice" state={avatarState} caption />
      <div className="shy-voice-actions">
        <button className="shy-button" type="button" disabled={disabled || localActive || !supported || sessionState.active}
          aria-pressed={state.listening} onClick={() => state.listening
            ? controller.current?.stopListening()
            : controller.current?.start(language, allowBrowserService, onTranscript)}>
          {state.listening ? 'Finish recording' : 'Speak to SHY'}
        </button>
        <button className="shy-button" type="button" disabled={!state.listening && !state.speaking && !localActive && !sessionState.active}
          onClick={() => { session.current?.stop(); setSessionConsent(false); controller.current?.cancel(); setCancelSignal(value => value + 1); }}>Stop voice</button>
        <button className="shy-button" type="button" disabled={!reply || disabled || localActive || !synthesisSupported || sessionState.active}
          onClick={() => reply && controller.current?.speak(reply.content, language, rate, volume, voiceURI, allowBrowserService)}>
          Read latest reply
        </button>
      </div>
      <p className="shy-muted" role="status">{sessionState.active ? (state.listening ? (sessionState.awaitingCommand ? 'Wake phrase heard. Say your message.' : 'Listening for “Hey SHY”…') : state.speaking ? 'SHY is speaking…' : 'Voice session is waiting for SHY…') : state.listening ? 'Listening… finish when ready.'
        : state.speaking ? 'SHY is speaking…' : 'Speak, review the transcript, then press Send.'}</p>
      {!supported && <p className="shy-muted">Voice input is unavailable in this browser. Text chat remains available.</p>}
      {state.error && <p role="alert">{state.error}</p>}
      <details>
        <summary>Voice settings and privacy</summary>
        <p>On-device speech is used when supported. Browser speech may send audio or text to your browser’s speech provider. SHY receives the transcript when you send it or explicitly enable automatic sending for a wake session. Audio is not saved by SHY.</p>
        <p>Wake listening uses browser speech transcripts, not a custom acoustic wake detector. Speech may be processed until the session ends. Limits: three minutes, twelve captures or six automatically sent messages.</p>
        <label><input type="checkbox" checked={sessionConsent} disabled={sessionState.active} onChange={event => setSessionConsent(event.target.checked)} />Allow a bounded wake voice session.</label>
        <label><input type="checkbox" checked={handsfree} disabled={sessionState.active || !onHandsfreeMessage || !synthesisSupported || blockedReply}
          onChange={event => { setHandsfree(event.target.checked); setSessionConsent(false); }} />Send wake-recognized messages automatically for this session.</label>
        <button className="shy-button" type="button" disabled={!sessionConsent || disabled || localActive || !supported || sessionState.active || (handsfree && blockedReply)}
          onClick={() => {
            if (session.current?.start(handsfree ? 'handsfree' : 'review', language, allowBrowserService) && handsfree) setReadReplies(true);
            setSessionConsent(false);
          }}>Start wake voice session</button>
        {sessionState.notice && <p role="status">{sessionState.notice}</p>}
        <p className="shy-muted">Default wake mode adds a draft for review. Automatic sending requires the separate session option. Stop voice ends future listening and playback; already sent messages may continue processing. Voice never accepts tool approvals.</p>
        <label><input type="checkbox" checked={allowBrowserService} onChange={event => {
          session.current?.stop(); setSessionConsent(false); controller.current?.cancel(); setAllowBrowserService(event.target.checked);
        }} /> Allow browser speech services for this session</label>
        <label><input type="checkbox" checked={readReplies} disabled={!synthesisSupported} onChange={event => {
          controller.current?.stopSpeaking(); setReadReplies(event.target.checked);
        }} /> Read new replies aloud</label>
        <label>Language<select value={language} onChange={event => {
          session.current?.stop(); setSessionConsent(false); controller.current?.cancel(); setLanguage(event.target.value); setVoiceURI('');
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
      <ShyLocalVoice disabled={disabled} onTranscript={onTranscript} onStart={() => { session.current?.stop(); setSessionConsent(false); controller.current?.cancel(); }}
        onActivity={setLocalActive} onStateChange={setLocalVoiceState} cancelSignal={cancelSignal} />
    </section>
  );
}

