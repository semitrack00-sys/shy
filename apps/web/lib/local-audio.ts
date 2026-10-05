/** Encode selected microphone input as bounded PCM WAV for the optional local engine. */
export function encodeWav(chunks: Float32Array[], sampleRate: number): ArrayBuffer {
  if (!Number.isFinite(sampleRate) || sampleRate < 16000 || sampleRate > 192000) throw new Error('Unsupported microphone sample rate');
  const count = chunks.reduce((total, chunk) => total + chunk.length, 0);
  if (count === 0 || count > sampleRate * 30) throw new Error('Recording must contain between zero and 30 seconds of audio');
  const samples = new Float32Array(count);
  let offset = 0;
  for (const chunk of chunks) { samples.set(chunk, offset); offset += chunk.length; }
  const outputCount = Math.floor(count * 16000 / sampleRate);
  if (!outputCount) throw new Error('Recording is too short');
  const buffer = new ArrayBuffer(44 + outputCount * 2);
  const view = new DataView(buffer);
  const text = (start: number, value: string) => { for (let i = 0; i < value.length; i++) view.setUint8(start + i, value.charCodeAt(i)); };
  text(0, 'RIFF'); view.setUint32(4, buffer.byteLength - 8, true); text(8, 'WAVE');
  text(12, 'fmt '); view.setUint32(16, 16, true); view.setUint16(20, 1, true);
  view.setUint16(22, 1, true); view.setUint32(24, 16000, true); view.setUint32(28, 32000, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true); text(36, 'data'); view.setUint32(40, outputCount * 2, true);
  for (let i = 0; i < outputCount; i++) {
    const start = Math.floor(i * sampleRate / 16000);
    const end = Math.min(count, Math.max(start + 1, Math.floor((i + 1) * sampleRate / 16000)));
    let value = 0;
    for (let j = start; j < end; j++) value += Number.isFinite(samples[j]) ? samples[j] : 0;
    value = Math.max(-1, Math.min(1, value / (end - start)));
    view.setInt16(44 + i * 2, Math.round(value * (value < 0 ? 32768 : 32767)), true);
  }
  return buffer;
}

export function audioBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(binary);
}

export class LocalRecorder {
  private epoch = 0;
  private stream: MediaStream | null = null;
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private processor: ScriptProcessorNode | null = null;
  private gain: GainNode | null = null;
  private chunks: Float32Array[] = [];
  private count = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private finished: ((buffer: ArrayBuffer) => void) | null = null;

  async start(deviceId: string, finished: (buffer: ArrayBuffer) => void, meter: (level: number) => void) {
    this.cancel();
    const epoch = this.epoch;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: deviceId
      ? { deviceId: { exact: deviceId }, channelCount: 1, echoCancellation: true }
      : { channelCount: 1, echoCancellation: true } });
    if (epoch !== this.epoch) { stream.getTracks().forEach(track => track.stop()); return false; }
    this.stream = stream;
    try {
      const context = new AudioContext({ sampleRate: 16000 });
      this.context = context;
      await context.resume();
      if (epoch !== this.epoch) { await context.close(); return false; }
      this.source = context.createMediaStreamSource(stream);
      this.processor = context.createScriptProcessor(4096, 1, 1);
      this.gain = context.createGain(); this.gain.gain.value = 0;
      this.finished = finished;
      this.processor.onaudioprocess = event => {
        if (this.epoch !== epoch) return;
        const input = event.inputBuffer.getChannelData(0);
        const remaining = Math.max(0, Math.floor(context.sampleRate * 30) - this.count);
        const chunk = input.slice(0, remaining);
        if (chunk.length) {
          this.chunks.push(chunk); this.count += chunk.length;
          let peak = 0; for (const value of chunk) peak = Math.max(peak, Math.abs(value));
          meter(Math.min(1, peak));
        }
        if (this.count >= context.sampleRate * 30) this.finish();
      };
      this.source.connect(this.processor); this.processor.connect(this.gain); this.gain.connect(context.destination);
      this.timer = setTimeout(() => { if (epoch === this.epoch) this.finish(); }, 30_000);
      return true;
    } catch (error) { if (epoch !== this.epoch) return false; this.cancel(); throw error; }
  }

  finish() {
    const finished = this.finished;
    const chunks = this.chunks;
    const sampleRate = this.context?.sampleRate;
    this.cancel();
    if (finished) finished(sampleRate && chunks.length ? encodeWav(chunks, sampleRate) : new ArrayBuffer(0));
  }

  cancel() {
    this.epoch++;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    this.source?.disconnect(); this.processor?.disconnect(); this.gain?.disconnect();
    if (this.processor) this.processor.onaudioprocess = null;
    this.stream?.getTracks().forEach(track => track.stop());
    if (this.context && this.context.state !== 'closed') void this.context.close().catch(() => {});
    this.stream = null; this.context = null; this.source = null; this.processor = null; this.gain = null;
    this.chunks = []; this.count = 0; this.finished = null;
  }
}
