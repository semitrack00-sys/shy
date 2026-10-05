import { NextRequest, NextResponse } from 'next/server';
import { getBackendBaseUrl } from '@/lib/config';

const MAX_BYTES = 1_400_000;

async function boundedResponse(response: Response) {
  const reader = response.body?.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  while (reader) {
    const result = await reader.read();
    if (result.done) break;
    total += result.value.byteLength;
    if (total > 65536) { await reader.cancel(); throw new Error('Oversized voice response'); }
    chunks.push(result.value);
  }
  return new NextResponse(Buffer.concat(chunks), { status: response.status,
    headers: { 'content-type': 'application/json' } });
}

export async function GET() {
  try {
    const response = await fetch(`${getBackendBaseUrl()}/voice/status`, {
      cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(5000),
    });
    return await boundedResponse(response);
  } catch {
    return NextResponse.json({ configured: false, provider_ready: null }, { status: 503 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const reader = request.body?.getReader();
    if (!reader) return NextResponse.json({ detail: 'voice_body_required' }, { status: 422 });
    const chunks: Uint8Array[] = [];
    let total = 0;
    while (true) {
      const result = await reader.read();
      if (result.done) break;
      total += result.value.byteLength;
      if (total > MAX_BYTES) {
        await reader.cancel();
        return NextResponse.json({ detail: 'voice_request_byte_limit_exceeded' }, { status: 413 });
      }
      chunks.push(result.value);
    }
    const response = await fetch(`${getBackendBaseUrl()}/voice/transcribe`, {
      method: 'POST', cache: 'no-store', redirect: 'error', headers: { 'content-type': 'application/json' },
      body: Buffer.concat(chunks), signal: AbortSignal.timeout(50_000),
    });
    return await boundedResponse(response);
  } catch {
    return NextResponse.json({ detail: 'local_speech_unavailable_or_timed_out' }, { status: 503 });
  }
}
