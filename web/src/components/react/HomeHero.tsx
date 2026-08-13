import { useEffect, useRef, useState } from 'react';
import type { Skill } from '@/lib/types';
import { browseAllPath } from '@/lib/utils';
import { SearchCommand } from './SearchCommand';
import { useI18n } from './LocaleProvider';

interface HomeHeroProps {
  skills: Skill[];
  total: number;
  lastSynced?: string | null;
  onBrowseCategories: () => void;
}

const PLATFORM_BADGES = [
  { label: 'Claude Code', color: 'from-orange-500/20 to-orange-500/5 text-orange-400 ring-orange-500/20' },
  { label: 'Kiro', color: 'from-violet-500/20 to-violet-500/5 text-violet-400 ring-violet-500/20' },
  { label: 'Codex', color: 'from-green-500/20 to-green-500/5 text-green-400 ring-green-500/20' },
  { label: 'Cursor', color: 'from-blue-500/20 to-blue-500/5 text-blue-400 ring-blue-500/20' },
];

function AnimatedCounter({ target }: { target: number }) {
  const [value, setValue] = useState(0);
  const rafRef = useRef<number>(0);
  const startRef = useRef<number>(0);
  const duration = 1200;

  useEffect(() => {
    startRef.current = performance.now();
    const tick = (now: number) => {
      const elapsed = now - startRef.current;
      const progress = Math.min(elapsed / duration, 1);
      // ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target]);

  return <>{value.toLocaleString()}</>;
}

export function HomeHero({ skills, total, lastSynced: _lastSynced, onBrowseCategories }: HomeHeroProps) {
  const { t, locale } = useI18n();

  return (
    <section className="hero-grid relative overflow-hidden border-b border-border/60 px-4 py-12 md:px-6 md:py-20">
      {/* Floating glow orbs */}
      <div
        className="pointer-events-none absolute -left-40 -top-40 h-96 w-96 rounded-full bg-accent/20 blur-[120px] animate-pulse-glow"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -bottom-20 -right-20 h-72 w-72 rounded-full bg-warm/15 blur-[100px] animate-pulse-glow"
        aria-hidden="true"
        style={{ animationDelay: '2s' }}
      />

      <div className="relative mx-auto max-w-3xl text-center">
        {/* Eyebrow label */}
        <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-accent/25 bg-accent/8 px-3.5 py-1.5 text-xs font-medium text-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-accent animate-pulse" />
          {locale === 'zh' ? 'AI Agent Skill 发现引擎' : 'AI Agent Skill Discovery Engine'}
        </div>

        <h1 className="font-display text-4xl font-bold tracking-tight md:text-5xl lg:text-6xl">
          <span className="text-gradient">{t('heroTitle')}</span>
        </h1>

        {/* Animated stats row */}
        <div className="mt-6 flex items-center justify-center gap-6">
          <div className="text-center">
            <div className="font-display text-3xl font-bold text-foreground md:text-4xl">
              <AnimatedCounter target={total} />
            </div>
            <div className="mt-0.5 text-xs text-muted">
              {locale === 'zh' ? '个 Skill' : 'Skills'}
            </div>
          </div>
          <div className="h-10 w-px bg-border" />
          <div className="text-center">
            <div className="font-display text-3xl font-bold text-foreground md:text-4xl">
              <AnimatedCounter target={76} />
            </div>
            <div className="mt-0.5 text-xs text-muted">
              {locale === 'zh' ? '个兼容 Agent' : 'Agents'}
            </div>
          </div>
          <div className="h-10 w-px bg-border" />
          <div className="text-center">
            <div className="font-display text-3xl font-bold text-foreground md:text-4xl">
              <AnimatedCounter target={9} />
            </div>
            <div className="mt-0.5 text-xs text-muted">
              {locale === 'zh' ? '个数据源' : 'Sources'}
            </div>
          </div>
        </div>

        <p className="mx-auto mt-6 max-w-xl text-sm leading-relaxed text-muted md:text-base">
          {t('heroSubtitle')}
        </p>

        {/* Search */}
        <div className="mx-auto mt-7 max-w-xl">
          <SearchCommand skills={skills} variant="hero" />
        </div>

        {/* Platform badges */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          {PLATFORM_BADGES.map((badge) => (
            <span
              key={badge.label}
              className={`inline-flex items-center rounded-full bg-gradient-to-b ${badge.color} px-3 py-1 text-xs font-medium ring-1`}
            >
              {badge.label}
            </span>
          ))}
        </div>

        {/* Browse CTA */}
        <div className="mt-7 flex flex-wrap items-center justify-center gap-3">
          <a
            href={browseAllPath()}
            className="inline-flex items-center gap-1.5 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-accent/25 transition hover:bg-accent/90 hover:shadow-accent/35 active:scale-95"
          >
            {locale === 'zh' ? '探索全部 Skill' : 'Explore All Skills'}
          </a>
          <button
            type="button"
            onClick={onBrowseCategories}
            className="inline-flex items-center gap-1 rounded-xl border border-border bg-card px-5 py-2.5 text-sm font-medium text-muted transition hover:border-accent/30 hover:text-foreground active:scale-95"
          >
            {t('heroBrowseCategories')}
            <span aria-hidden="true">↓</span>
          </button>
        </div>
      </div>
    </section>
  );
}
