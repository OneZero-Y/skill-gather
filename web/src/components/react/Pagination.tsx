import { ChevronLeft, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface PaginationProps {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  labels: {
    prev: string;
    next: string;
    pageOf: string;
  };
}

function pageRange(current: number, total: number): (number | 'ellipsis')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }
  const pages: (number | 'ellipsis')[] = [1];
  if (current > 3) pages.push('ellipsis');
  for (let p = Math.max(2, current - 1); p <= Math.min(total - 1, current + 1); p += 1) {
    pages.push(p);
  }
  if (current < total - 2) pages.push('ellipsis');
  pages.push(total);
  return pages;
}

export function Pagination({
  page,
  totalPages,
  totalItems,
  pageSize,
  onPageChange,
  labels,
}: PaginationProps) {
  if (totalItems === 0) return null;

  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);
  const pages = pageRange(page, totalPages);

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-between">
      <p className="text-xs text-muted">
        {labels.pageOf
          .replace('{start}', String(start))
          .replace('{end}', String(end))
          .replace('{total}', String(totalItems))
          .replace('{page}', String(page))
          .replace('{pages}', String(totalPages))}
      </p>

      <nav className="flex items-center gap-1" aria-label="Pagination">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          className={cn(
            'inline-flex h-9 items-center gap-1 rounded-lg border border-border px-3 text-sm transition',
            page <= 1
              ? 'cursor-not-allowed opacity-40'
              : 'hover:border-accent/40 hover:bg-card hover:text-foreground',
          )}
        >
          <ChevronLeft className="h-4 w-4" />
          {labels.prev}
        </button>

        <div className="hidden items-center gap-1 sm:flex">
          {pages.map((p, i) =>
            p === 'ellipsis' ? (
              <span key={`e-${i}`} className="px-2 text-sm text-muted">
                …
              </span>
            ) : (
              <button
                key={p}
                type="button"
                onClick={() => onPageChange(p)}
                className={cn(
                  'h-9 min-w-9 rounded-lg border px-2 text-sm transition',
                  p === page
                    ? 'border-accent bg-accent/10 font-medium text-accent'
                    : 'border-border hover:border-accent/40 hover:bg-card',
                )}
              >
                {p}
              </button>
            ),
          )}
        </div>

        <button
          type="button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          className={cn(
            'inline-flex h-9 items-center gap-1 rounded-lg border border-border px-3 text-sm transition',
            page >= totalPages
              ? 'cursor-not-allowed opacity-40'
              : 'hover:border-accent/40 hover:bg-card hover:text-foreground',
          )}
        >
          {labels.next}
          <ChevronRight className="h-4 w-4" />
        </button>
      </nav>
    </div>
  );
}
