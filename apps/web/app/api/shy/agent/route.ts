import { getBackendHeaders } from '@/lib/deployment-access';
import { NextRequest, NextResponse } from 'next/server';
import { getBackendBaseUrl } from '@/lib/config';
import { safeAgentFailure } from '@/lib/agent-errors';

export async function POST(request: NextRequest) {
  try {
    const body = await request.text();
    const response = await fetch(`${getBackendBaseUrl()}/chat`, {
      method: 'POST',
      cache: 'no-store',
      headers: {
        'content-type': 'application/json',
        ...getBackendHeaders(),
      },
      body,
    });
    const payload = await response.text();
    if (!response.ok) {
      return NextResponse.json(safeAgentFailure(payload), { status: response.status });
    }
    return new NextResponse(payload, {
      status: response.status,
      headers: {
        'content-type': response.headers.get('content-type') ?? 'application/json',
      },
    });
  } catch {
    return NextResponse.json(
      {
        assistant: 'SHY',
        status: 'FAILED',
        reason: 'SHY is temporarily unavailable.',
      },
      { status: 503 }
    );
  }
}
