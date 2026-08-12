import { useMemo, useState } from 'react';
import { Layers, Sparkles } from 'lucide-react';
import type { SkillsFile } from '@/lib/types';
import { cn } from '@/lib/utils';
import { HeaderControls } from './HeaderControls';
import { LocaleProvider, useI18n } from './LocaleProvider';
import { SearchCommand } from './SearchCommand';
import { SkillCard } from './SkillCard';

interface SkillAppProps {
  data: SkillsFile;
}

const PAGE_SIZE = 48;

export function SkillApp({ data }: SkillAppProps) {
  return (
    <LocaleProvider>
      <SkillAppContent data={data} />
    </LocaleProvider>
  );
}

function SkillAppContent({ data }: SkillAppProps) {
  const { t, categoryLabel } = useI18n();
  const [category, setCategory] = useState<string>('all');
  const [source, setSource] = useState<string>('all');
  const [platform, setPlatform] = useState<string>('all');
  const [visible, setVisible] = useState(PAGE_SIZE);

  const filtered = useMemo(() => {
    return data.skills.filter((skill) => {
      if (category !== 'all' && skill.category !== category) return false;
      if (source !== 'all' && skill.source !== source) return false;
      if (platform !== 'all' && !skill.platforms.includes(platform)) return false;
      return true;
    });
  }, [data.skills, category, source, platform]);

  const shown = filtered.slice(0, visible);
  const updatedDate = data.meta?.last_synced?.slice(0, 10) ?? data.generated_at.slice(0, 10);

  return (
    <div className="relative flex min-h-screen">
      <div className="pointer-events-none fixed inset-0 mesh-bg" aria-hidden="true" />
      <div
        className="pointer-events-none fixed -left-32 top-20 h-96 w-96 rounded-full bg-accent/20 blur-[120px] animate-pulse-glow"
        aria-hidden="true"
      />

      <aside className="glass-strong fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r lg:flex">
        <div className="border-b border-border px-5 py-5">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-accent" />
            <h1 className="font-display text-lg font-bold">{data.site.title}</h1>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-muted">{t('siteDescription')}</p>
          <p className="mt-2 text-[11px] text-muted">
            {t('statsSummary', {
              total: data.total,
              sources: data.meta?.sources_count ?? data.sources.length,
            })}
          </p>
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
          <FilterGroup
            title={t('filterCategory')}
            items={[
              { id: 'all', label: t('filterAll'), count: data.total },
              ...data.categories.map((c) => ({
                id: c.id,
                label: categoryLabel(c.id),
                count: c.count,
              })),
            ]}
            active={category}
            onSelect={setCategory}
          />
          <FilterGroup
            title={t('filterSource')}
            items={[
              { id: 'all', label: t('filterAll'), count: data.total },
              ...data.sources.map((s) => ({ id: s.id, label: s.id, count: s.count })),
            ]}
            active={source}
            onSelect={setSource}
          />
          <FilterGroup
            title={t('filterPlatform')}
            items={[
              { id: 'all', label: t('filterAll'), count: data.total },
              { id: 'claude_code', label: 'Claude Code', count: 0 },
              { id: 'codex', label: 'Codex', count: 0 },
              { id: 'kiro', label: 'Kiro', count: 0 },
              { id: 'universal', label: 'Universal', count: 0 },
            ]}
            active={platform}
            onSelect={setPlatform}
          />
        </nav>
      </aside>

      <main className="flex min-h-screen flex-1 flex-col lg:pl-64">
        <header className="glass sticky top-0 z-20 flex items-center gap-3 border-b px-4 py-3 md:px-6">
          <div className="font-display text-base font-semibold lg:hidden">{data.site.title}</div>
          <SearchCommand skills={data.skills} />
          <HeaderControls />
        </header>

        <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-6">
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

          <section>
            <div className="mb-4 flex items-end justify-between gap-3">
              <div>
                <h2 className="font-display text-lg font-semibold">{t('allSkills')}</h2>
                <p className="text-xs text-muted">
                  {t('showingCount', { shown: shown.length, total: filtered.length })}
                </p>
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {shown.map((skill, index) => (
                <SkillCard key={skill.id} skill={skill} index={index} />
              ))}
            </div>

            {visible < filtered.length && (
              <div className="mt-6 flex justify-center">
                <button
                  type="button"
                  onClick={() => setVisible((v) => v + PAGE_SIZE)}
                  className="rounded-xl border border-border bg-card px-4 py-2 text-sm text-muted transition hover:border-accent/40 hover:text-foreground"
                >
                  {t('loadMore')}
                </button>
              </div>
            )}
          </section>
        </div>

        <footer className="border-t border-border px-6 py-4 text-center text-xs text-muted">
          Skill Store · {t('footerUpdated', { date: updatedDate })}
        </footer>
      </main>
    </div>
  );
}

interface FilterGroupProps {
  title: string;
  items: Array<{ id: string; label: string; count: number }>;
  active: string;
  onSelect: (id: string) => void;
}

function FilterGroup({ title, items, active, onSelect }: FilterGroupProps) {
  return (
    <div>
      <h3 className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wide text-muted">{title}</h3>
      <div className="space-y-0.5">
        {items.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => onSelect(item.id)}
            className={cn(
              'flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-sm transition',
              active === item.id
                ? 'bg-accent/10 font-medium text-accent'
                : 'text-muted hover:bg-card hover:text-foreground',
            )}
          >
            <span className="truncate">{item.label}</span>
            {item.count > 0 && <span className="text-xs opacity-70">{item.count}</span>}
          </button>
        ))}
      </div>
    </div>
  );
}
