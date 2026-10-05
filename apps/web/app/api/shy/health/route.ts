import { NextResponse } from 'next/server';
import { getBackendBaseUrl } from '@/lib/config';

export async function GET() {
  try {
    const response = await fetch(`${getBackendBaseUrl()}/health`, {
      cache: 'no-store',
    });
    const payload = await response.text();
    return new NextResponse(payload, {
      status: response.status,
      headers: {
        'content-type': response.headers.get('content-type') ?? 'application/json',
      },
    });
  } catch {
    return NextResponse.json(
      {
        status: 'error',
        system: 'SHY',
        version: 'unavailable',
        application_healthy: false,
        ollama_connected: false,
        database_connected: false,
        local_model_available: false,
      },
      { status: 503 }
    );
  }
}