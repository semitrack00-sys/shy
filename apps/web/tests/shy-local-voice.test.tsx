import React from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ShyLocalVoice } from '@/components/shy-local-voice';

const state = vi.hoisted(() => ({ callback: null as null | ((buffer: ArrayBuffer) => void), device: '', cancel: vi.fn() }));
vi.mock('@/lib/local-audio', async importOriginal => {
  const original = await importOriginal<typeof import('@/lib/local-audio')>();
  return { ...original, LocalRecorder: class {
    async start(device: string, callback: (buffer: ArrayBuffer) => void) { state.device = device; state.callback = callback; return true; }
    finish() { state.callback?.(new ArrayBuffer(48)); }
    cancel() { state.cancel(); }
  } };
});

let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  state.callback = null; state.cancel.mockClear();
  fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ configured: true }) });
  vi.stubGlobal('fetch', fetchMock);
  Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {
    getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] }),
    enumerateDevices: vi.fn().mockResolvedValue([{ deviceId: 'microphone-two', kind: 'audioinput', label: 'USB microphone' }]),
  } });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const props = { disabled: false, cancelSignal: 0, onStart: vi.fn(), onActivity: vi.fn() };

describe('local voice controls', () => {
  it('selects a microphone and puts a local transcript in the draft without auto-sending chat', async () => {
    const transcript = vi.fn(); render(<ShyLocalVoice {...props} onTranscript={transcript} />);
    await screen.findByText(/Local speech is configured/);
    fireEvent.click(screen.getByRole('button', { name: 'Choose microphone', hidden: true }));
    await screen.findByText('USB microphone');
    fireEvent.change(screen.getByLabelText('Microphone', { exact: true }), { target: { value: 'microphone-two' } });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Record with local engine', hidden: true })));
    expect(state.device).toBe('microphone-two');
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ text: 'Bonjou SHY' }) });
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Transcribe recording', hidden: true })));
    expect(transcript).toHaveBeenCalledExactlyOnceWith('Bonjou SHY');
    expect(fetchMock.mock.calls[1][0]).toBe('/api/shy/voice');
    expect(JSON.parse(fetchMock.mock.calls[1][1].body).language).toBe('auto');
  });

  it('ignores a transcript returned after cancellation', async () => {
    const transcript = vi.fn(); render(<ShyLocalVoice {...props} onTranscript={transcript} />);
    await screen.findByText(/Local speech is configured/);
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Record with local engine', hidden: true })));
    let resolve: (result: unknown) => void = () => {};
    fetchMock.mockReturnValueOnce(new Promise(done => { resolve = done; }));
    fireEvent.click(screen.getByRole('button', { name: 'Transcribe recording', hidden: true }));
    fireEvent.click(screen.getByRole('button', { name: 'Cancel local voice', hidden: true }));
    await act(async () => resolve({ ok: true, json: async () => ({ text: 'Late transcript' }) }));
    expect(transcript).not.toHaveBeenCalled();
  });

  it('keeps recording disabled when a provider is not configured', async () => {
    fetchMock.mockResolvedValueOnce({ ok: true, json: async () => ({ configured: false }) });
    render(<ShyLocalVoice {...props} onTranscript={vi.fn()} />);
    await screen.findByText(/No local speech server is configured/);
    expect(screen.getByRole('button', { name: 'Record with local engine', hidden: true })).toBeDisabled();
  });
});
