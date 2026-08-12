import type { Locale } from '@/lib/i18n';
import { useI18n } from './LocaleProvider';

interface StatsBadgeProps {
  total: number;
  lastSynced?: string | null;
  className?: string;
}

export function StatsBadge({ total, lastSynced, className }: StatsBadgeProps) {
  const { t, locale } = useI18n();
  const formattedTotal = total.toLocaleString(locale === 'zh' ? 'zh-CN' : 'en-US');
  const relativeTime = formatRelativeTime(lastSynced, locale);

  return (
    <div
      className={`inline-flex items-center gap-3 border border-border bg-card px-4 py-2 font-mono text-sm ${className ?? ''}`}
    >
      <span className="h-2.5 w-2.5 shrink-0 bg-accent" aria-hidden="true" />
      <span className="text-foreground">
        <strong className="font-semibold">{formattedTotal}</strong> Skills
      </span>
      <span className="h-4 w-px shrink-0 bg-border" aria-hidden="true" />
      <span className="text-muted">{t('statsUpdated', { time: relativeTime })}</span>
    </div>
  );
}

function formatRelativeTime(iso: string | null | undefined, locale: Locale): string {
  if (!iso) return locale === 'zh' ? '未知' : 'unknown';

  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return locale === 'zh' ? '未知' : 'unknown';

  const diffMin = Math.floor((Date.now() - then) / 60_000);
  if (diffMin < 1) return locale === 'zh' ? '刚刚' : 'just now';
  if (diffMin < 60) {
    return locale === 'zh' ? `${diffMin} 分钟前` : `${diffMin}m ago`;
  }

  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) {
    return locale === 'zh' ? `${diffHours} 小时前` : `${diffHours} hours ago`;
  }

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) {
    return locale === 'zh' ? `${diffDays} 天前` : `${diffDays} days ago`;
  }

  return new Date(iso).toLocaleDateString(locale === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}
