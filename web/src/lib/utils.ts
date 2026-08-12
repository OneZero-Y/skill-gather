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

/** Build internal detail page path for a skill id (may contain slashes). */
export function skillDetailPath(id: string): string {
  return `/skills/${id.split('/').map(encodeURIComponent).join('/')}`;
}

/** Decode catch-all route param back to skill id. */
export function parseSkillIdFromParam(param: string | string[] | undefined): string {
  const segments = Array.isArray(param) ? param : param ? [param] : [];
  return segments.map(decodeURIComponent).join('/');
}
