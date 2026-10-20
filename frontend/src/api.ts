export class ApiError extends Error {
  constructor(public status: number, public data: unknown) {
    super(formatError(data));
  }
}
export function formatError(data: unknown): string {
  if (typeof data === 'string') return data;
  if (Array.isArray(data)) return data.map(formatError).join(' ');
  if (data && typeof data === 'object') return Object.entries(data).map(([key,value]) => `${key === 'detail' || key === 'non_field_errors' ? '' : `${key}: `}${formatError(value)}`).join(' ');
  return 'Amalni bajarib bo‘lmadi. Qayta urinib ko‘ring.';
}
export async function api<T = unknown>(path: string, options: RequestInit = {}): Promise<T> {
  const token = document.cookie.split('; ').find(value => value.startsWith('csrftoken='))?.split('=')[1];
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (token) headers.set('X-CSRFToken', decodeURIComponent(token));
  const response = await fetch(`/api/${path.replace(/^\//, '')}`, { ...options, headers, credentials: 'same-origin' });
  if (response.status === 204) return undefined as T;
  const data = await response.json().catch(() => ({ detail: 'Server javobini o‘qib bo‘lmadi.' }));
  if (!response.ok) throw new ApiError(response.status, data);
  return data as T;
}
export const post = <T = unknown>(path: string, data: unknown) => api<T>(path, { method: 'POST', body: JSON.stringify(data) });
export const patch = <T = unknown>(path: string, data: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(data) });
export function dateLabel(value: string | null): string {
  if (!value) return '—';
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  if (Number.isNaN(date.getTime())) return value;
  const parts = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'numeric', year: 'numeric', timeZone: 'Asia/Tashkent' }).formatToParts(date);
  const part = (type: string) => parts.find(item => item.type === type)?.value || '';
  const months = ['yanvar','fevral','mart','aprel','may','iyun','iyul','avgust','sentabr','oktabr','noyabr','dekabr'];
  return `${part('day')}-${months[Number(part('month')) - 1]}, ${part('year')}`;
}
