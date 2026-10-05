import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { encodeWav, audioBase64, LocalRecorder } from '@/lib/local-audio';

describe('bounded PCM encoding', () => {
  it('encodes the sample rate, mono format, duration, and clipped samples correctly', () => {
    const buffer = encodeWav([new Float32Array([-2, 0, 2])], 16000);
    const view = new DataView(buffer);
    expect(buffer.byteLength).toBe(50); expect(view.getUint32(24, true)).toBe(16000);
    expect(view.getUint16(22, true)).toBe(1); expect(view.getUint16(34, true)).toBe(16);
    expect(view.getInt16(44, true)).toBe(-32768); expect(view.getInt16(48, true)).toBe(32767);
    expect(atob(audioBase64(buffer)).slice(0, 4)).toBe('RIFF');
  });
  it('resamples 48 kHz input to 16 kHz and treats nonfinite samples as silence', () => {
    const buffer = encodeWav([new Float32Array([NaN, 0, 0, 1, 1, 1])], 48000);
    expect(buffer.byteLength).toBe(48);
    expect(new DataView(buffer).getInt16(44, true)).toBe(0);
    expect(new DataView(buffer).getInt16(46, true)).toBe(32767);
  });
  it('rejects empty, oversized, and unsupported-rate recordings', () => {
    expect(() => encodeWav([], 16000)).toThrow();
    expect(() => encodeWav([new Float32Array(480001)], 16000)).toThrow();
    expect(() => encodeWav([new Float32Array(4)], 8000)).toThrow();
  });
});

describe('selected microphone lifecycle', () => {
  let stop: ReturnType<typeof vi.fn>;
  let processor: { connect: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn>; onaudioprocess: ((event: unknown) => void) | null };
  let getUserMedia: ReturnType<typeof vi.fn>;
  beforeEach(() => {
    stop = vi.fn(); processor = { connect: vi.fn(), disconnect: vi.fn(), onaudioprocess: null };
    getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] });
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } });
    vi.stubGlobal('AudioContext', class {
      sampleRate = 16000; state = 'running';
      resume = vi.fn().mockResolvedValue(undefined);
      close = vi.fn().mockResolvedValue(undefined);
      createMediaStreamSource() { return { connect: vi.fn(), disconnect: vi.fn() }; }
      createScriptProcessor() { return processor; }
      createGain() { return { gain: { value: 1 }, connect: vi.fn(), disconnect: vi.fn() }; }
      destination = {};
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it('requests the chosen device, reports level, and releases tracks before returning audio', async () => {
    const recorder = new LocalRecorder(); const finished = vi.fn(); const level = vi.fn();
    expect(await recorder.start('chosen-device', finished, level)).toBe(true);
    expect(getUserMedia.mock.calls[0][0].audio.deviceId).toEqual({ exact: 'chosen-device' });
    processor.onaudioprocess?.({ inputBuffer: { getChannelData: () => new Float32Array([0.25, -0.5]) } });
    expect(level).toHaveBeenCalledWith(0.5);
    recorder.finish(); expect(stop).toHaveBeenCalledTimes(1); expect(finished).toHaveBeenCalledTimes(1);
    expect(finished.mock.calls[0][0].byteLength).toBe(48);
  });

  it('releases a microphone that arrives after cancellation without accepting audio', async () => {
    let resolve: (stream: unknown) => void = () => {};
    getUserMedia.mockReturnValue(new Promise(done => { resolve = done; }));
    const recorder = new LocalRecorder(); const finished = vi.fn();
    const pending = recorder.start('', finished, vi.fn()); recorder.cancel();
    resolve({ getTracks: () => [{ stop }] });
    expect(await pending).toBe(false); expect(stop).toHaveBeenCalledTimes(1); expect(finished).not.toHaveBeenCalled();
  });

  it('cancellation discards captured audio rather than uploading it', async () => {
    const recorder = new LocalRecorder(); const finished = vi.fn();
    await recorder.start('', finished, vi.fn());
    processor.onaudioprocess?.({ inputBuffer: { getChannelData: () => new Float32Array([0.1]) } });
    recorder.cancel(); expect(finished).not.toHaveBeenCalled(); expect(stop).toHaveBeenCalledTimes(1);
  });
});
