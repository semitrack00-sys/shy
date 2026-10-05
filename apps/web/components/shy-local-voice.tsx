'use client';

import React, { useEffect, useRef, useState } from 'react';
import { LocalRecorder, audioBase64 } from '@/lib/local-audio';
import { FRONTEND_API_BASE } from '@/lib/config';
import { VOICE_LANGUAGES } from '@/lib/browser-voice';

export function ShyLocalVoice({ disabled, onTranscript, onStart, onActivity, cancelSignal }: {
  disabled: boolean; onTranscript: (text: string) => void; onStart: () => void;
  onActivity: (active: boolean) => void; cancelSignal: number;
}) {
  const recorder = useRef<LocalRecorder | null>(null);
  const request = useRef<AbortController | null>(null);
  const generation = useRef({ value: 0 });
  const [configured, setConfigured] = useState(false);
  const [statusLoaded, setStatusLoaded] = useState(false);
  const [devices, setDevices] = useState<MediaDeviceInfo[]>([]);
  const [deviceId, setDeviceId] = useState('');
  const [language, setLanguage] = useState('auto');
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState('');

  function cancel() {
    generation.current.value++;
    recorder.current?.cancel(); request.current?.abort(); request.current = null;
    setRecording(false); setBusy(false); setLevel(0);
  }

  useEffect(() => {
    recorder.current = new LocalRecorder();
    const session = generation.current;
    const controller = new AbortController();
    void fetch(`${FRONTEND_API_BASE}/voice`, { signal: controller.signal, cache: 'no-store' })
      .then(async response => {
        const status = await response.json();
        if (!controller.signal.aborted) { setConfigured(response.ok && status.configured === true); setStatusLoaded(true); }
      }).catch(() => { if (!controller.signal.aborted) setStatusLoaded(true); });
    const hide = () => { if (document.hidden) cancel(); };
    document.addEventListener('visibilitychange', hide);
    return () => { controller.abort(); session.value++; recorder.current?.cancel(); request.current?.abort(); document.removeEventListener('visibilitychange', hide); };
  }, []);

  useEffect(() => { if (disabled) cancel(); }, [disabled]);
  useEffect(() => { cancel(); }, [cancelSignal]);
  useEffect(() => { onActivity(recording || busy); }, [recording, busy, onActivity]);

  async function refreshDevices() {
    cancel(); setError('');
    const epoch = generation.current.value;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access requires HTTPS or localhost and a supported browser.');
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(track => track.stop());
      const inputs = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === 'audioinput');
      if (generation.current.value === epoch) setDevices(inputs);
    } catch { if (generation.current.value === epoch) setError('Microphone access failed. Check browser permission and your system input device.'); }
  }

  async function start() {
    cancel(); onStart(); setError(''); setBusy(true);
    const epoch = generation.current.value;
    try {
      // Cancel browser speech output to prevent it being captured as input.
      window.speechSynthesis?.cancel();
      const started = await recorder.current?.start(deviceId, async audio => {
        if (generation.current.value !== epoch) return;
        setRecording(false); setLevel(0);
        if (!audio.byteLength) { setBusy(false); setError('No audio was captured. Try recording again.'); return; }
        setBusy(true);
        const controller = new AbortController(); request.current = controller;
        const timer = setTimeout(() => controller.abort(), 50_000);
        try {
          const response = await fetch(`${FRONTEND_API_BASE}/voice`, {
            method: 'POST', headers: { 'content-type': 'application/json' }, signal: controller.signal,
            body: JSON.stringify({ audio_base64: audioBase64(audio), language }),
          });
          const result = await response.json();
          if (generation.current.value !== epoch) return;
          if (!response.ok || typeof result.text !== 'string' || !result.text.trim() || result.text.length > 8000) {
            throw new Error('Local transcription failed. Check the speech server, language, and recording.');
          }
          onTranscript(result.text.trim());
        } catch {
          if (generation.current.value === epoch) setError('Local transcription failed or timed out. You can still type your message.');
        } finally {
          clearTimeout(timer);
          if (generation.current.value === epoch) { request.current = null; setBusy(false); }
        }
      }, value => { if (generation.current.value === epoch) setLevel(value); });
      if (generation.current.value === epoch) { setBusy(false); setRecording(started === true); }
    } catch { if (generation.current.value === epoch) { setBusy(false); setError('Recording could not start. Check microphone permission and the selected input.'); } }
  }

  return <details className="shy-local-voice">
    <summary>Local speech engine and microphone</summary>
    <p className="shy-muted">{!statusLoaded ? 'Checking local speech configuration…' : configured
      ? 'Local speech is configured. Its availability is checked when you transcribe.'
      : 'No local speech server is configured. Browser voice and typed chat remain available.'}</p>
    <p>Audio goes to your SHY core and its configured local speech server when recording ends. SHY does not save it. Review the transcript before sending.</p>
    <button type="button" className="shy-button" disabled={disabled || busy || recording} onClick={() => void refreshDevices()}>Choose microphone</button>
    <label>Microphone<select value={deviceId} disabled={busy || recording} onChange={event => { cancel(); setDeviceId(event.target.value); }}>
      <option value="">System default</option>
      {devices.map((device, index) => <option key={device.deviceId || index} value={device.deviceId}>{device.label || `Microphone ${index + 1}`}</option>)}
    </select></label>
    <label>Local transcription language<select value={language} disabled={busy || recording} onChange={event => setLanguage(event.target.value)}>
      <option value="auto">Detect language</option>
      {VOICE_LANGUAGES.map(([code, label]) => <option key={code} value={code.split('-')[0]}>{label}</option>)}
    </select></label>
    <div className="shy-voice-actions">
      <button type="button" className="shy-button" disabled={disabled || busy || !configured}
        onClick={() => recording ? recorder.current?.finish() : void start()}>{recording ? 'Transcribe recording' : 'Record with local engine'}</button>
      <button type="button" className="shy-button" disabled={!recording && !busy} onClick={cancel}>Cancel local voice</button>
    </div>
    <label>Microphone level<meter min="0" max="1" value={level} /></label>
    <p role="status">{recording ? 'Recording locally… maximum 30 seconds.' : busy ? 'Preparing microphone or transcribing…' : 'Microphone is off.'}</p>
    {error && <p role="alert">{error}</p>}
  </details>;
}
