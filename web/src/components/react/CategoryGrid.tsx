import { ChevronRight } from 'lucide-react';
import { getCategoryIcon } from '@/lib/category-icons';
import { browseAllPath, cn } from '@/lib/utils';
import { useI18n } from './LocaleProvider';

interface CategoryItem {
  id: string;
  label: string;
  count: number;
}

interface CategoryGridProps {
  categories: CategoryItem[];
}

export function CategoryGrid({ categories }: CategoryGridProps) {
  const { t } = useI18n();
  const viewAllHref = browseAllPath();

  return (
    <section id="categories">
      <div className="mb-4 flex items-end justify-between gap-3">
        <h2 className="font-display text-lg font-semibold md:text-xl">{t('browseByCategory')}</h2>
        <a
          href={viewAllHref}
          className="inline-flex shrink-0 items-center gap-0.5 text-xs font-medium text-muted transition hover:text-accent"
        >
          {t('viewAll')}
          <ChevronRight className="h-3.5 w-3.5" />
        </a>
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {categories.map((cat) => {
          const Icon = getCategoryIcon(cat.id);
          return (
            <a
              key={cat.id}
              href={browseAllPath({ category: cat.id })}
              className={cn(
                'group flex flex-col gap-3 rounded-2xl border border-border bg-card p-4 text-left transition',
                'hover:-translate-y-0.5 hover:border-accent/40 hover:bg-card-hover hover:shadow-md hover:shadow-accent/5',
              )}
            >
              <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-accent/10 text-accent transition group-hover:bg-accent/15">
                <Icon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-foreground">{cat.label}</div>
                <div className="mt-0.5 text-xs text-muted">
                  {t('categorySkillCount', { count: cat.count })}
                </div>
              </div>
            </a>
          );
        })}
      </div>
    </section>
  );
}
