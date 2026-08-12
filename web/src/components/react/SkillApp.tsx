import { useEffect, useMemo, useState } from 'react';
import { Layers, Sparkles } from 'lucide-react';
import type { SkillsFile } from '@/lib/types';
import { PLATFORM_LABELS } from '@/lib/types';
import { groupCategories } from '@/lib/categories';
import { getCategoryGroupLabel } from '@/lib/i18n';
import { CategorySidebar, CategoryStrip } from './CategorySidebar';
import { HeaderControls } from './HeaderControls';
import { ListFilters, type SortKey } from './ListFilters';
import { LocaleProvider, useI18n } from './LocaleProvider';
import { Pagination } from './Pagination';
import { SearchCommand } from './SearchCommand';
import { SkillCard } from './SkillCard';

interface SkillAppProps {
  data: SkillsFile;
}

const PAGE_SIZE = 24;
const PLATFORM_IDS = ['claude_code', 'codex', 'kiro', 'universal'] as const;

export function SkillApp({ data }: SkillAppProps) {
  return (
    <LocaleProvider>
      <SkillAppContent data={data} />
    </LocaleProvider>
  );
}

function SkillAppContent({ data }: SkillAppProps) {
  const { t, categoryLabel, locale } = useI18n();
  const [category, setCategory] = useState('all');
  const [source, setSource] = useState('all');
  const [platform, setPlatform] = useState('all');
  const [sort, setSort] = useState<SortKey>('score');
  const [page, setPage] = useState(1);

  const categoryOptions = useMemo(
    () =>
      data.categories.map((c) => ({
        id: c.id,
        label: categoryLabel(c.id),
        count: c.count,
      })),
    [data.categories, categoryLabel],
  );

  const categoryGroups = useMemo(
    () =>
      groupCategories(categoryOptions).map((g) => ({
        groupId: g.groupId,
        groupLabel: getCategoryGroupLabel(locale, g.groupId),
        items: g.items,
      })),
    [categoryOptions, locale],
  );

  const categoryStripItems = useMemo(
    () => [{ id: 'all', label: t('filterAll'), count: data.total }, ...categoryOptions],
    [categoryOptions, data.total, t],
  );

  const platformCounts = useMemo(() => {
    const counts: Record<string, number> = { all: data.total };
    for (const id of PLATFORM_IDS) counts[id] = 0;
    for (const skill of data.skills) {
      for (const p of skill.platforms) {
        if (p in counts) counts[p] += 1;
      }
    }
    return counts;
  }, [data.skills, data.total]);

  const filtered = useMemo(() => {
    let list = data.skills.filter((skill) => {
      if (category !== 'all' && skill.category !== category) return false;
      if (source !== 'all' && skill.source !== source) return false;
      if (platform !== 'all' && !skill.platforms.includes(platform)) return false;
      return true;
    });

    list = [...list].sort((a, b) => {
      if (sort === 'stars') return b.stars - a.stars || b.score - a.score;
      if (sort === 'name') return a.name.localeCompare(b.name);
      return b.score - a.score || b.stars - a.stars;
    });
    return list;
  }, [data.skills, category, source, platform, sort]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  const hasActiveFilters = source !== 'all' || platform !== 'all';
  const showFeatured = safePage === 1 && category === 'all' && !hasActiveFilters;

  useEffect(() => {
    setPage(1);
  }, [category, source, platform, sort]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [safePage]);

  const updatedDate = data.meta?.last_synced?.slice(0, 10) ?? data.generated_at.slice(0, 10);

  return (
    <div className="relative min-h-screen">
      <div className="pointer-events-none fixed inset-0 mesh-bg" aria-hidden="true" />

      <header className="glass sticky top-0 z-30 border-b">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 md:px-6">
          <div className="flex min-w-0 items-center gap-2">
            <Layers className="h-5 w-5 shrink-0 text-accent" />
            <span className="font-display text-base font-bold md:text-lg">{data.site.title}</span>
          </div>
          <HeaderControls />
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl gap-0 px-4 md:px-6">
        <CategorySidebar
          title={t('filterCategory')}
          allItem={{ id: 'all', label: t('filterAll'), count: data.total }}
          groups={categoryGroups}
          active={category}
          onSelect={setCategory}
        />

        <main className="min-w-0 flex-1 py-6 lg:pl-6">
          <section className="mb-6 lg:hidden">
            <CategoryStrip items={categoryStripItems} active={category} onSelect={setCategory} />
          </section>

          {showFeatured && (
            <section className="mb-8">
              <div className="mb-4 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent" />
                <h2 className="font-display text-lg font-semibold">{t('featured')}</h2>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {data.featured.slice(0, 6).map((skill, index) => (
                  <SkillCard key={skill.id} skill={skill} index={index} />
                ))}
              </div>
            </section>
          )}

          <section>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="shrink-0">
                <h2 className="font-display text-lg font-semibold">{t('allSkills')}</h2>
                <p className="mt-0.5 text-xs text-muted">
                  {t('showingCount', { shown: pageItems.length, total: filtered.length })}
                </p>
              </div>
              <SearchCommand skills={data.skills} className="sm:mt-0.5" />
            </div>

            <ListFilters
              sources={[
                { id: 'all', label: t('filterAll'), count: data.total },
                ...data.sources.map((s) => ({ id: s.id, label: s.id, count: s.count })),
              ]}
              platforms={[
                { id: 'all', label: t('filterAll'), count: platformCounts.all },
                ...PLATFORM_IDS.map((id) => ({
                  id,
                  label: PLATFORM_LABELS[id] ?? id,
                  count: platformCounts[id],
                })),
              ]}
              source={source}
              platform={platform}
              sort={sort}
              onSourceChange={setSource}
              onPlatformChange={setPlatform}
              onSortChange={setSort}
              onClear={() => {
                setSource('all');
                setPlatform('all');
              }}
              hasActiveFilters={hasActiveFilters}
              labels={{
                filterSource: t('filterSource'),
                filterPlatform: t('filterPlatform'),
                filterAll: t('filterAll'),
                sortBy: t('sortBy'),
                sortScore: t('sortScore'),
                sortStars: t('sortStars'),
                sortName: t('sortName'),
                clearAll: t('clearAll'),
              }}
            />

            {pageItems.length === 0 ? (
              <div className="mt-6 rounded-2xl border border-dashed border-border py-16 text-center text-sm text-muted">
                {t('noResults')}
              </div>
            ) : (
              <div className="mt-6 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {pageItems.map((skill, index) => (
                  <SkillCard key={skill.id} skill={skill} index={index} />
                ))}
              </div>
            )}

            <div className="mt-8">
              <Pagination
                page={safePage}
                totalPages={totalPages}
                totalItems={filtered.length}
                pageSize={PAGE_SIZE}
                onPageChange={setPage}
                labels={{
                  prev: t('prev'),
                  next: t('next'),
                  pageOf: t('pageRange'),
                }}
              />
            </div>
          </section>
        </main>
      </div>

      <footer className="border-t border-border px-6 py-6 text-center text-xs text-muted">
        Skill Store · {t('footerUpdated', { date: updatedDate })}
      </footer>
    </div>
  );
}
