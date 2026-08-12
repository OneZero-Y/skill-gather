import { SearchCommand } from './SearchCommand';
import { StatsBadge } from './StatsBadge';
import { useI18n } from './LocaleProvider';
import type { Skill } from '@/lib/types';

interface HomeHeroProps {
  skills: Skill[];
  total: number;
  lastSynced?: string | null;
  onBrowseCategories: () => void;
}

export function HomeHero({ skills, total, lastSynced, onBrowseCategories }: HomeHeroProps) {
  const { t } = useI18n();

  return (
    <section className="hero-grid relative border-b border-border/60 px-4 py-10 md:px-6 md:py-14">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="font-display text-3xl font-bold tracking-tight md:text-4xl lg:text-5xl">
          <span className="text-gradient">{t('heroTitle')}</span>
        </h1>

        <div className="mt-5 flex justify-center">
          <StatsBadge total={total} lastSynced={lastSynced} />
        </div>

        <p className="mx-auto mt-5 max-w-xl text-sm leading-relaxed text-muted md:text-base">
          {t('heroSubtitle')}
        </p>
        <div className="mx-auto mt-6 max-w-xl">
          <SearchCommand skills={skills} variant="hero" />
        </div>
        <button
          type="button"
          onClick={onBrowseCategories}
          className="mt-4 text-xs text-muted transition hover:text-accent md:text-sm"
        >
          {t('heroBrowseCategories')} →
        </button>
      </div>
    </section>
  );
}
