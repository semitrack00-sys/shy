import { NextRequest, NextResponse } from 'next/server';
import { getBackendBaseUrl } from '@/lib/config';

async function forward(request: NextRequest, context: { params: Promise<{ segments?: string[] }> }) {
  const { segments = [] } = await context.params;
  const id = '[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}';
  const suffix = segments.join('/');
  if (!(suffix === '' || ['search', 'answer', 'compare'].includes(suffix) || new RegExp(`^${id}(/delete)?$`).test(suffix))) {
    return NextResponse.json({ detail: 'invalid_document_path' }, { status: 404 });
  }
  try {
    let body: Uint8Array | undefined;
    if (request.method !== 'GET') {
      const reader = request.body?.getReader();
      if (!reader) return NextResponse.json({ detail: 'document_body_required' }, { status: 422 });
      const chunks: Uint8Array[] = [];
      let size = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 512 * 1024) {
          await reader.cancel();
          return NextResponse.json({ detail: 'document_request_too_large' }, { status: 413 });
        }
        chunks.push(value);
      }
      body = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
    }
    const query = new URLSearchParams();
    for (const key of ['project_id']) {
      const value = request.nextUrl.searchParams.get(key);
      if (value !== null) query.set(key, value);
    }
    const response = await fetch(`${getBackendBaseUrl()}/documents${suffix ? '/' + suffix : ''}?${query}`, {
      method: request.method, body, headers: { 'content-type': 'application/json' },
      cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(15000),
    });
    const reader = response.body?.getReader();
    const chunks: Uint8Array[] = [];
    let size = 0;
    if (reader) while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 1024 * 1024) { await reader.cancel(); throw new Error('document_response_too_large'); }
      chunks.push(value);
    }
    const result = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.byteLength; }
    return new NextResponse(result, { status: response.status,
      headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
  } catch {
    return NextResponse.json({ detail: 'document_service_unavailable' }, { status: 503 });
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
