import { useMemo } from 'react';
import type { SkillsFile } from '@/lib/types';
import { browseAllPath } from '@/lib/utils';
import { AppShell } from './AppShell';
import { CategoryGrid } from './CategoryGrid';
import { HomeHero } from './HomeHero';
import { useI18n } from './LocaleProvider';
import { SkillSection } from './SkillSection';

const OFFICIAL_SOURCES = [
  'anthropics-skills',
  'openai-skills',
  'vercel-agent-skills',
  'langchain-skills',
] as const;

interface SkillHomeProps {
  data: SkillsFile;
}

export function SkillHome({ data }: SkillHomeProps) {
  const updatedDate = data.meta?.last_synced?.slice(0, 10) ?? data.generated_at.slice(0, 10);

  return (
    <AppShell title={data.site.title} updatedDate={updatedDate}>
      <SkillHomeContent data={data} />
    </AppShell>
  );
}

function SkillHomeContent({ data }: SkillHomeProps) {
  const { t, categoryLabel } = useI18n();

  const categoryOptions = useMemo(
    () =>
      data.categories.map((c) => ({
        id: c.id,
        label: categoryLabel(c.id),
        count: c.count,
      })),
    [data.categories, categoryLabel],
  );

  const officialSkills = useMemo(
    () =>
      data.skills
        .filter((s) => OFFICIAL_SOURCES.includes(s.source as (typeof OFFICIAL_SOURCES)[number]))
        .sort((a, b) => b.score - a.score || b.stars - a.stars)
        .slice(0, 8),
    [data.skills],
  );

  const popularSkills = useMemo(
    () =>
      [...data.skills]
        .filter((s) => s.stars > 0)
        .sort((a, b) => b.stars - a.stars || b.score - a.score)
        .slice(0, 10),
    [data.skills],
  );

  const scrollToCategories = () => {
    document.getElementById('categories')?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <>
      <HomeHero
        skills={data.skills}
        total={data.total}
        lastSynced={data.meta?.last_synced}
        onBrowseCategories={scrollToCategories}
      />

      <div className="mx-auto max-w-7xl space-y-10 px-4 py-8 md:space-y-12 md:px-6 md:py-10">
        <SkillSection
          title={t('featured')}
          skills={data.featured.slice(0, 8)}
          viewAllLabel={t('viewAll')}
          viewAllHref={browseAllPath({ sort: 'score' })}
        />

        {officialSkills.length > 0 && (
          <SkillSection
            title={t('officialSkills')}
            skills={officialSkills}
            viewAllLabel={t('viewAll')}
            viewAllHref={browseAllPath({ source: 'anthropics-skills' })}
          />
        )}

        <CategoryGrid categories={categoryOptions} />

        {popularSkills.length > 0 && (
          <SkillSection
            title={t('popularSkills')}
            skills={popularSkills}
            layout="list"
            viewAllLabel={t('viewAll')}
            viewAllHref={browseAllPath({ sort: 'stars' })}
          />
        )}
      </div>
    </>
  );
}
