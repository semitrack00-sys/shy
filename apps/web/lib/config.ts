export const APP_NAME = 'SHY';
export const DEFAULT_THEME: 'light' | 'dark' = 'dark';
export const FRONTEND_API_BASE = '/api/shy';

export function getBackendBaseUrl(): string {
  return process.env.SHY_BACKEND_BASE_URL ?? 'http://127.0.0.1:8019';
}

export function getLocalTimeLabel(iso: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  }).format(new Date(iso));
}