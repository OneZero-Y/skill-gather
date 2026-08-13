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
      className={`inline-flex items-center gap-2 rounded-full border border-accent/25 bg-accent/8 px-4 py-1.5 text-sm ${className ?? ''}`}
    >
      {/* Live dot */}
      <span className="relative flex h-2 w-2 shrink-0">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-50" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-accent" />
      </span>
      <span className="font-semibold text-foreground">{formattedTotal}</span>
      <span className="text-muted">{locale === 'zh' ? '个 Skills' : 'Skills'}</span>
      <span className="h-3 w-px bg-border" aria-hidden="true" />
      <span className="text-xs text-muted">{t('statsUpdated', { time: relativeTime })}</span>
    </div>
  );
}

function formatRelativeTime(iso: string | null | undefined, locale: Locale): string {
  if (!iso) return locale === 'zh' ? '未知' : 'unknown';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return locale === 'zh' ? '未知' : 'unknown';

  const diffMin = Math.floor((Date.now() - then) / 60_000);
  if (diffMin < 1)  return locale === 'zh' ? '刚刚' : 'just now';
  if (diffMin < 60) return locale === 'zh' ? `${diffMin} 分钟前` : `${diffMin}m ago`;

  const diffHours = Math.floor(diffMin / 60);
  if (diffHours < 24) return locale === 'zh' ? `${diffHours} 小时前` : `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return locale === 'zh' ? `${diffDays} 天前` : `${diffDays}d ago`;

  return new Date(iso).toLocaleDateString(locale === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric', month: 'short', day: 'numeric',
  });
}
