import { useEffect, useMemo, useState } from 'react';
import type { SkillsFile } from '@/lib/types';
import { PLATFORM_LABELS } from '@/lib/types';
import { groupCategories } from '@/lib/categories';
import { getCategoryGroupLabel } from '@/lib/i18n';
import { browseAllPath, parseBrowseSearch } from '@/lib/utils';
import { AppShell } from './AppShell';
import { CategorySidebar, CategoryStrip } from './CategorySidebar';
import { ListFilters, type SortKey } from './ListFilters';
import { useI18n } from './LocaleProvider';
import { Pagination } from './Pagination';
import { SearchCommand } from './SearchCommand';
import { SkillCard } from './SkillCard';
import { StatsBadge } from './StatsBadge';

const PAGE_SIZE = 24;
const PLATFORM_IDS = ['claude_code', 'codex', 'kiro', 'universal'] as const;

function readInitialBrowseState() {
  if (typeof window === 'undefined') {
    return { category: 'all', source: 'all', platform: 'all', sort: 'score' as SortKey, page: 1 };
  }
  const parsed = parseBrowseSearch(window.location.search);
  const sort = ['score', 'stars', 'name'].includes(parsed.sort)
    ? (parsed.sort as SortKey)
    : 'score';
  return { ...parsed, sort };
}

interface SkillBrowseProps {
  data: SkillsFile;
}

export function SkillBrowse({ data }: SkillBrowseProps) {
  const updatedDate = data.meta?.last_synced?.slice(0, 10) ?? data.generated_at.slice(0, 10);

  return (
    <AppShell title={data.site.title} updatedDate={updatedDate}>
      <SkillBrowseContent data={data} />
    </AppShell>
  );
}

function SkillBrowseContent({ data }: SkillBrowseProps) {
  const { t, categoryLabel, locale } = useI18n();
  const [category, setCategory] = useState(() => readInitialBrowseState().category);
  const [source, setSource] = useState(() => readInitialBrowseState().source);
  const [platform, setPlatform] = useState(() => readInitialBrowseState().platform);
  const [sort, setSort] = useState<SortKey>(() => readInitialBrowseState().sort);
  const [page, setPage] = useState(() => readInitialBrowseState().page);

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

  useEffect(() => {
    setPage(1);
  }, [category, source, platform, sort]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [safePage]);

  useEffect(() => {
    const href = browseAllPath({ category, source, platform, sort, page: safePage });
    window.history.replaceState(null, '', href);
  }, [category, source, platform, sort, safePage]);

  const filterLabels = {
    filterSource: t('filterSource'),
    filterPlatform: t('filterPlatform'),
    filterAll: t('filterAll'),
    sortBy: t('sortBy'),
    sortScore: t('sortScore'),
    sortStars: t('sortStars'),
    sortName: t('sortName'),
    clearAll: t('clearAll'),
  };

  return (
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

          <section>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
              <div className="shrink-0 space-y-3">
                <h1 className="font-display text-lg font-semibold md:text-xl">{t('allSkills')}</h1>
                <StatsBadge total={data.total} lastSynced={data.meta?.last_synced} />
                <p className="text-xs text-muted">
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
              labels={filterLabels}
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
  );
}
