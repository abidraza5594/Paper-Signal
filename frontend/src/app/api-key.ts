import { HttpHandlerFn, HttpRequest } from '@angular/common/http';

export const API_KEY_STORAGE = 'papersignal.apiKey';

export function readStoredApiKey(): string {
  try {
    return localStorage.getItem(API_KEY_STORAGE) ?? '';
  } catch {
    return '';
  }
}

export function storeApiKey(key: string): void {
  try {
    const clean = key.trim();
    if (clean) localStorage.setItem(API_KEY_STORAGE, clean);
    else localStorage.removeItem(API_KEY_STORAGE);
  } catch {
    /* private browsing or storage disabled: the key just will not persist */
  }
}

/** Attach the caller's key to every /api request when the service runs in key mode. */
export function apiKeyInterceptor(request: HttpRequest<unknown>, next: HttpHandlerFn) {
  const key = readStoredApiKey();
  if (!key || !request.url.startsWith('/api')) return next(request);
  return next(request.clone({ setHeaders: { 'X-API-Key': key } }));
}
