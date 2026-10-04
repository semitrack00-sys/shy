import { NextRequest, NextResponse } from 'next/server';

function unauthorized() {
  return new NextResponse('Authentication required.', {
    status: 401,
    headers: {
      'WWW-Authenticate': 'Basic realm="SHY Production Beta", charset="UTF-8"',
      'Cache-Control': 'no-store',
    },
  });
}

export function middleware(request: NextRequest) {
  const expectedUser = process.env.SHY_BASIC_AUTH_USER?.trim();
  const expectedPassword = process.env.SHY_BASIC_AUTH_PASSWORD?.trim();

  if (!expectedUser || !expectedPassword) {
    return NextResponse.next();
  }

  const header = request.headers.get('authorization');
  if (!header?.startsWith('Basic ')) {
    return unauthorized();
  }

  try {
    const decoded = atob(header.slice(6));
    const separator = decoded.indexOf(':');
    if (separator < 0) return unauthorized();

    const user = decoded.slice(0, separator);
    const password = decoded.slice(separator + 1);

    if (user !== expectedUser || password !== expectedPassword) {
      return unauthorized();
    }

    return NextResponse.next();
  } catch {
    return unauthorized();
  }
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
