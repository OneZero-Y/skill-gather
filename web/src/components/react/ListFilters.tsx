import { X } from 'lucide-react';
import { cn } from '@/lib/utils';

export type SortKey = 'score' | 'stars' | 'name';

interface FilterOption {
  id: string;
  label: string;
  count?: number;
}

interface ListFiltersProps {
  sources: FilterOption[];
  platforms: FilterOption[];
  source: string;
  platform: string;
  sort: SortKey;
  onSourceChange: (id: string) => void;
  onPlatformChange: (id: string) => void;
  onSortChange: (sort: SortKey) => void;
  onClear: () => void;
  hasActiveFilters: boolean;
  labels: {
    filterSource: string;
    filterPlatform: string;
    filterAll: string;
    sortBy: string;
    sortScore: string;
    sortStars: string;
    sortName: string;
    clearAll: string;
  };
}

export function ListFilters({
  sources,
  platforms,
  source,
  platform,
  sort,
  onSourceChange,
  onPlatformChange,
  onSortChange,
  onClear,
  hasActiveFilters,
  labels,
}: ListFiltersProps) {
  return (
    <div className="mt-4 flex flex-col gap-3 rounded-xl border border-border/60 bg-card/40 px-3 py-3 sm:flex-row sm:flex-wrap sm:items-center">
      <div className="flex min-w-[160px] flex-1 items-center gap-2 sm:max-w-xs">
        <label htmlFor="source-select" className="sr-only">
          {labels.filterSource}
        </label>
        <select
          id="source-select"
          value={source}
          onChange={(e) => onSourceChange(e.target.value)}
          className="h-9 w-full rounded-lg border border-border bg-background px-3 text-sm outline-none focus:border-accent/50"
        >
          {sources.map((item) => (
            <option key={item.id} value={item.id}>
              {item.id === 'all' ? labels.filterAll : item.label}
              {item.count != null ? ` (${item.count})` : ''}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wide text-muted">
          {labels.filterPlatform}
        </span>
        {platforms.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onPlatformChange(item.id)}
            className={cn(
              'rounded-full border px-3 py-1 text-xs transition',
              platform === item.id
                ? 'border-accent bg-accent/10 font-medium text-accent'
                : 'border-border text-muted hover:border-accent/30',
            )}
          >
            {item.id === 'all' ? labels.filterAll : item.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2 sm:ml-auto">
        <select
          value={sort}
          onChange={(e) => onSortChange(e.target.value as SortKey)}
          aria-label={labels.sortBy}
          className="h-9 rounded-lg border border-border bg-background px-3 text-sm outline-none focus:border-accent/50"
        >
          <option value="score">{labels.sortScore}</option>
          <option value="stars">{labels.sortStars}</option>
          <option value="name">{labels.sortName}</option>
        </select>
        {hasActiveFilters && (
          <button
            type="button"
            onClick={onClear}
            className="inline-flex h-9 items-center gap-1 rounded-lg border border-border px-3 text-xs text-muted transition hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
            {labels.clearAll}
          </button>
        )}
      </div>
    </div>
  );
}
