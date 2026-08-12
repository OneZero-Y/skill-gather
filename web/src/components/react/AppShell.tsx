import type { ReactNode } from 'react';
import { Layers } from 'lucide-react';
import { HeaderControls } from './HeaderControls';
import { LocaleProvider, useI18n } from './LocaleProvider';

interface AppShellProps {
  title: string;
  updatedDate: string;
  children: ReactNode;
}

export function AppShell({ title, updatedDate, children }: AppShellProps) {
  return (
    <LocaleProvider>
      <AppShellContent title={title} updatedDate={updatedDate}>
        {children}
      </AppShellContent>
    </LocaleProvider>
  );
}

function AppShellContent({ title, updatedDate, children }: AppShellProps) {
  const { t } = useI18n();

  return (
    <div className="relative min-h-screen">
      <div className="pointer-events-none fixed inset-0 mesh-bg" aria-hidden="true" />

      <header className="glass sticky top-0 z-30 border-b">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-4 py-3 md:px-6">
          <a href="/" className="flex min-w-0 items-center gap-2">
            <Layers className="h-5 w-5 shrink-0 text-accent" />
            <span className="font-display text-base font-bold md:text-lg">{title}</span>
          </a>
          <HeaderControls />
        </div>
      </header>

      {children}

      <footer className="mt-8 border-t border-border px-6 py-6 text-center text-xs text-muted">
        Skill Store · {t('footerUpdated', { date: updatedDate })}
      </footer>
    </div>
  );
}
