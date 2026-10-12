import { NextRequest, NextResponse } from 'next/server';
import { hostedAccessRequired, ownerAuthorized, hostedPublicOrigin } from './lib/deployment-access';
export async function middleware(request:NextRequest) {
  if (!hostedAccessRequired()) return NextResponse.next();
  if (!process.env.SHY_OWNER_USERNAME || (process.env.SHY_OWNER_PASSWORD?.length ?? 0)<24 || (process.env.SHY_ACCESS_TOKEN?.length ?? 0)<32 || !hostedPublicOrigin()) {
    return new NextResponse('Hosted owner access is not configured.',{status:503,headers:{'cache-control':'no-store'}});
  }
  if (request.nextUrl.pathname === '/livez' && request.method === 'GET') return NextResponse.json({status:'alive',system:'SHY'},{headers:{'cache-control':'no-store'}});
  if (!await ownerAuthorized(request.headers.get('authorization'))) {
    return new NextResponse('SHY owner sign-in required.',{status:401,headers:{'www-authenticate':'Basic realm="SHY owner", charset="UTF-8"','cache-control':'no-store'}});
  }
  if (!['GET','HEAD','OPTIONS'].includes(request.method) && request.headers.get('origin') !== hostedPublicOrigin()) {
    return new NextResponse('Request origin rejected.',{status:403,headers:{'cache-control':'no-store'}});
  }
  const response=NextResponse.next();
  response.headers.set('cache-control','private, no-store');
  response.headers.set('x-robots-tag','noindex, nofollow');
  return response;
}
export const config={matcher:['/:path*']};
