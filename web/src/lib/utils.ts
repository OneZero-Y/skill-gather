import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatNumber(value: number): string {
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(1)}M`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  return String(value);
}

export function isSafeUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:';
  } catch {
    return false;
  }
}

/** Build browse-all page path with optional filters. */
export function browseAllPath(params?: {
  category?: string;
  source?: string;
  platform?: string;
  sort?: string;
  page?: number;
}): string {
  const base = '/skills/all';
  if (!params) return base;

  const q = new URLSearchParams();
  if (params.category && params.category !== 'all') q.set('category', params.category);
  if (params.source && params.source !== 'all') q.set('source', params.source);
  if (params.platform && params.platform !== 'all') q.set('platform', params.platform);
  if (params.sort && params.sort !== 'score') q.set('sort', params.sort);
  if (params.page && params.page > 1) q.set('page', String(params.page));

  const qs = q.toString();
  return qs ? `${base}?${qs}` : base;
}

export function parseBrowseSearch(search: string): {
  category: string;
  source: string;
  platform: string;
  sort: string;
  page: number;
} {
  const p = new URLSearchParams(search);
  const page = Number.parseInt(p.get('page') ?? '1', 10);
  return {
    category: p.get('category') ?? 'all',
    source: p.get('source') ?? 'all',
    platform: p.get('platform') ?? 'all',
    sort: p.get('sort') ?? 'score',
    page: Number.isFinite(page) && page > 0 ? page : 1,
  };
}

export function skillDetailPath(id: string): string {
  return `/skills/${id.split('/').map(encodeURIComponent).join('/')}`;
}

/** Decode catch-all route param back to skill id. */
export function parseSkillIdFromParam(param: string | string[] | undefined): string {
  const segments = Array.isArray(param) ? param : param ? [param] : [];
  return segments.map(decodeURIComponent).join('/');
}
