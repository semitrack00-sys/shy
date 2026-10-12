export function hostedPublicOrigin(): string | undefined { return process.env.SHY_PUBLIC_ORIGIN || process.env.RENDER_EXTERNAL_URL; }
export function hostedAccessRequired(): boolean {
  return process.env.SHY_REQUIRE_AUTH === '1' || process.env.RENDER === 'true' || !!process.env.SHY_OWNER_PASSWORD;
}
export function getBackendHeaders(): Record<string,string> {
  const token=process.env.SHY_ACCESS_TOKEN;
  if (hostedAccessRequired() && (!token || token.length < 32)) throw new Error('Backend access is not configured.');
  return token ? {authorization:`Bearer ${token}`} : {};
}
async function sameDigest(a:string,b:string):Promise<boolean> {
  const enc=new TextEncoder();
  const [left,right]=await Promise.all([crypto.subtle.digest('SHA-256',enc.encode(a)),crypto.subtle.digest('SHA-256',enc.encode(b))]);
  const x=new Uint8Array(left),y=new Uint8Array(right);let difference=0;
  for (let i=0;i<x.length;i++) difference|=x[i]^y[i];
  return difference===0;
}
export async function ownerAuthorized(header:string|null):Promise<boolean> {
  const user=process.env.SHY_OWNER_USERNAME,password=process.env.SHY_OWNER_PASSWORD;
  if (!user || !password || password.length < 8 || !header || header.length > 512 || !header.startsWith('Basic ')) return false;
  try { return await sameDigest(atob(header.slice(6)),`${user}:${password}`); } catch { return false; }
}
