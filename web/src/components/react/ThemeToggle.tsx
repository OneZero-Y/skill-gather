import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useI18n } from './LocaleProvider';

export function ThemeToggle() {
  const { t } = useI18n();
  const [dark, setDark] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setDark(document.documentElement.classList.contains('dark'));
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('skill-gather-theme', next ? 'dark' : 'light');
  };

  if (!mounted) {
    return <div className="h-10 w-10" />;
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className={cn(
        'flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-card',
        'text-muted transition-colors hover:border-accent/40 hover:text-foreground',
      )}
      aria-label={t('toggleTheme')}
    >
      {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
