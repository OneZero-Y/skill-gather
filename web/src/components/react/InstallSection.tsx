import { useCallback, useEffect, useState } from 'react';
import { ArrowUpRight, Check, Copy } from 'lucide-react';
import type { Locale } from '@/lib/i18n';
import {
  INSTALL_PRESETS,
  SKILL_STORE_GITHUB,
  buildInstallCommand,
  type InstallPreset,
} from '@/lib/install';
import { cn, isSafeUrl } from '@/lib/utils';
import { useI18n } from './LocaleProvider';

interface InstallSectionProps {
  skillId: string;
  installUrl: string;
}

export function InstallSection({ skillId, installUrl }: InstallSectionProps) {
  const { t, locale } = useI18n();
  const safeUrl = isSafeUrl(installUrl);

  return (
    <div className="mt-8 rounded-2xl border border-border bg-background/50 p-4 md:p-5">
      <h2 className="font-display text-sm font-semibold text-foreground">{t('installGuide')}</h2>

      <CliInstall skillId={skillId} />

      <div className="mt-6 border-t border-border/60 pt-5">
        <p className="text-xs leading-relaxed text-muted">{t('installSourceHint')}</p>
        <CopyBlock text={installUrl} disabled={!safeUrl} className="mt-2" />

        {safeUrl && (
          <a
            href={installUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1.5 text-xs text-accent transition hover:underline"
          >
            {t('openOnGithub')}
            <ArrowUpRight className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      <div className="mt-4 rounded-xl border border-border/60 bg-background/40 px-3 py-2.5">
        <p className="text-[11px] font-medium text-muted">{t('installManualNote')}</p>
        <ul className="mt-2 space-y-1">
          {INSTALL_PRESETS.filter((p) => !p.id.startsWith('project-')).map((p) => (
            <li key={p.id} className="flex flex-wrap items-baseline gap-x-2 text-[11px]">
              <span className="text-foreground/80">{p.label[locale]}</span>
              <code className="text-muted">{p.path}</code>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function CliInstall({ skillId }: { skillId: string }) {
  const { t, locale } = useI18n();
  const [activePreset, setActivePreset] = useState(INSTALL_PRESETS[0].id);
  const preset = INSTALL_PRESETS.find((p) => p.id === activePreset) ?? INSTALL_PRESETS[0];
  const command = buildInstallCommand(skillId, preset);

  return (
    <div className="mt-3">
      <h3 className="text-xs font-medium text-foreground">{t('installCliTitle')}</h3>
      <p className="mt-1 text-xs leading-relaxed text-muted">
        {t('installCliPrereqBefore')}
        <a
          href={SKILL_STORE_GITHUB}
          target="_blank"
          rel="noopener noreferrer"
          className="mx-0.5 text-accent hover:underline"
        >
          skill-gather
        </a>
        {t('installCliPrereqAfter')}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        {INSTALL_PRESETS.map((p) => (
          <PresetTab
            key={p.id}
            preset={p}
            locale={locale}
            active={activePreset === p.id}
            onClick={() => setActivePreset(p.id)}
          />
        ))}
      </div>
      <CopyBlock text={command} className="mt-2" />
    </div>
  );
}

function CopyBlock({
  text,
  disabled,
  className,
}: {
  text: string;
  disabled?: boolean;
  className?: string;
}) {
  const { t } = useI18n();
  const [copied, setCopied] = useState(false);

  const copy = useCallback(async () => {
    if (disabled) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }, [text, disabled]);

  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 2000);
    return () => window.clearTimeout(timer);
  }, [copied]);

  return (
    <>
      <div className={cn('relative', className)}>
        <pre
          className={cn(
            'overflow-x-auto rounded-xl border border-border bg-card px-3 py-3 pr-11 font-mono text-xs leading-relaxed break-all whitespace-pre-wrap',
            disabled ? 'text-muted' : 'text-foreground',
          )}
        >
          {text}
        </pre>
        <button
          type="button"
          disabled={disabled}
          aria-label={copied ? t('copySuccess') : t('copyAria')}
          onClick={() => void copy()}
          className={cn(
            'absolute right-2 top-2 inline-flex items-center justify-center rounded-lg border p-1.5 transition',
            copied
              ? 'border-accent/40 bg-accent/10 text-accent'
              : 'border-border bg-background text-muted hover:border-accent/40 hover:text-foreground',
            disabled && 'pointer-events-none opacity-50',
          )}
        >
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
        </button>
      </div>

      {copied && (
        <div
          role="status"
          className="pointer-events-none fixed bottom-6 left-1/2 z-50 -translate-x-1/2 rounded-full border border-accent/30 bg-card px-4 py-2 text-sm text-accent shadow-lg"
        >
          {t('copySuccess')}
        </div>
      )}
    </>
  );
}

function PresetTab({
  preset,
  locale,
  active,
  onClick,
}: {
  preset: InstallPreset;
  locale: Locale;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'rounded-full border px-3 py-1.5 text-xs transition',
        active
          ? 'border-accent bg-accent/10 font-medium text-accent'
          : 'border-border text-muted hover:border-accent/30 hover:text-foreground',
      )}
    >
      {preset.label[locale]}
    </button>
  );
}
