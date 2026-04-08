// Server-side uses Docker internal URL, client-side uses public URL
const SERVER_API_BASE = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api/v1';
const CLIENT_API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:3001/api/v1';

function getApiBase(): string {
  return typeof window === 'undefined' ? SERVER_API_BASE : CLIENT_API_BASE;
}

export async function fetchAPI(path: string, options?: RequestInit) {
  const res = await fetch(`${getApiBase()}${path}`, {
    ...options,
    cache: 'no-store',
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
