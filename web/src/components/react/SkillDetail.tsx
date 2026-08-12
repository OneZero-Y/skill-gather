import { type ReactNode } from 'react';
import { ArrowLeft, ArrowUpRight, Copy, Star } from 'lucide-react';
import type { Skill } from '@/lib/types';
import { PLATFORM_LABELS } from '@/lib/types';
import { cn, formatNumber, isSafeUrl } from '@/lib/utils';
import { HeaderControls } from './HeaderControls';
import { LocaleProvider, useI18n } from './LocaleProvider';

interface SkillDetailProps {
  skill: Skill;
}

export function SkillDetail({ skill }: SkillDetailProps) {
  return (
    <LocaleProvider>
      <SkillDetailContent skill={skill} />
    </LocaleProvider>
  );
}

function SkillDetailContent({ skill }: SkillDetailProps) {
  const { t, categoryLabel } = useI18n();
  const safeInstall = isSafeUrl(skill.install_url);

  const copyInstallCommand = () => {
    const cmd = `skill-store install ${skill.id}`;
    void navigator.clipboard.writeText(cmd);
  };

  return (
    <div className="relative min-h-screen">
      <div className="pointer-events-none fixed inset-0 mesh-bg" aria-hidden="true" />

      <header className="glass sticky top-0 z-20 flex items-center gap-3 border-b px-4 py-3 md:px-6">
        <a
          href="/"
          className="inline-flex items-center gap-1.5 rounded-xl px-2 py-1.5 text-sm text-muted transition hover:bg-card hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('back')}
        </a>
        <div className="min-w-0 flex-1 truncate font-display text-sm font-semibold md:text-base">
          {skill.name}
        </div>
        <HeaderControls />
      </header>

      <main className="mx-auto w-full max-w-3xl px-4 py-8 md:px-6">
        <article className="animate-fade-up rounded-2xl border border-border bg-card p-6 md:p-8">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="min-w-0 flex-1">
              <h1 className="font-display text-2xl font-bold text-foreground md:text-3xl">{skill.name}</h1>
              <p className="mt-2 break-all font-mono text-xs text-muted">{skill.id}</p>
            </div>
            <span className="rounded-xl bg-accent/10 px-3 py-1.5 text-lg font-bold text-accent">
              {skill.score}
            </span>
          </div>

          <p className="mt-6 text-sm leading-relaxed text-foreground/90">{skill.description}</p>

          <dl className="mt-8 grid gap-4 sm:grid-cols-2">
            <MetaItem label={t('category')}>{categoryLabel(skill.category)}</MetaItem>
            <MetaItem label={t('source')}>{skill.source}</MetaItem>
            {skill.license && <MetaItem label={t('license')}>{skill.license}</MetaItem>}
            {skill.stars > 0 && (
              <MetaItem label="Stars">
                <span className="inline-flex items-center gap-1">
                  <Star className="h-3.5 w-3.5 text-warm" />
                  {formatNumber(skill.stars)}
                </span>
              </MetaItem>
            )}
            {skill.installs > 0 && (
              <MetaItem label={t('installs')}>{formatNumber(skill.installs)}</MetaItem>
            )}
          </dl>

          {skill.platforms.length > 0 && (
            <div className="mt-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">
                {t('compatiblePlatforms')}
              </h2>
              <div className="flex flex-wrap gap-2">
                {skill.platforms.map((p) => (
                  <span
                    key={p}
                    className="rounded-lg bg-background px-2.5 py-1 text-xs ring-1 ring-border"
                  >
                    {PLATFORM_LABELS[p] ?? p}
                  </span>
                ))}
              </div>
            </div>
          )}

          {skill.tags.length > 0 && (
            <div className="mt-6">
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{t('tags')}</h2>
              <div className="flex flex-wrap gap-2">
                {skill.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-lg bg-background px-2.5 py-1 text-xs text-muted ring-1 ring-border"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="mt-8 flex flex-wrap gap-3">
            <a
              href={safeInstall ? skill.install_url : '#'}
              target="_blank"
              rel="noopener noreferrer"
              className={cn(
                'inline-flex items-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-medium text-accent-foreground transition hover:opacity-90',
                !safeInstall && 'pointer-events-none opacity-50',
              )}
            >
              {t('viewSource')}
              <ArrowUpRight className="h-4 w-4" />
            </a>
            <button
              type="button"
              onClick={copyInstallCommand}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-background px-4 py-2.5 text-sm text-muted transition hover:border-accent/40 hover:text-foreground"
            >
              <Copy className="h-4 w-4" />
              {t('copyInstall')}
            </button>
          </div>
        </article>
      </main>
    </div>
  );
}

function MetaItem({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-xl bg-background/60 px-4 py-3 ring-1 ring-border">
      <dt className="text-[11px] font-semibold uppercase tracking-wide text-muted">{label}</dt>
      <dd className="mt-1 text-sm text-foreground">{children}</dd>
    </div>
  );
}
