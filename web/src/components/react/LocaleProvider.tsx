import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Languages } from 'lucide-react';
import {
  LOCALE_STORAGE_KEY,
  type Locale,
  type MessageKey,
  getCategoryLabel,
  localeToHtmlLang,
  resolveLocale,
  translate,
} from '@/lib/i18n';
import { cn } from '@/lib/utils';

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  toggleLocale: () => void;
  t: (key: MessageKey, vars?: Record<string, string | number>) => string;
  categoryLabel: (id: string) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function readInitialLocale(): Locale {
  if (typeof window === 'undefined') return 'en';
  return resolveLocale(localStorage.getItem(LOCALE_STORAGE_KEY), navigator.language);
}

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(readInitialLocale);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    localStorage.setItem(LOCALE_STORAGE_KEY, next);
    document.documentElement.lang = localeToHtmlLang(next);
  }, []);

  const toggleLocale = useCallback(() => {
    setLocale(locale === 'zh' ? 'en' : 'zh');
  }, [locale, setLocale]);

  useEffect(() => {
    document.documentElement.lang = localeToHtmlLang(locale);
  }, [locale]);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      setLocale,
      toggleLocale,
      t: (key, vars) => translate(locale, key, vars),
      categoryLabel: (id) => getCategoryLabel(locale, id),
    }),
    [locale, setLocale, toggleLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error('useI18n must be used within LocaleProvider');
  }
  return ctx;
}

export function LocaleToggle() {
  const { locale, toggleLocale, t } = useI18n();

  return (
    <button
      type="button"
      onClick={toggleLocale}
      className={cn(
        'flex h-10 items-center gap-1.5 rounded-xl border border-border bg-card px-2.5',
        'text-xs font-medium text-muted transition-colors hover:border-accent/40 hover:text-foreground',
      )}
      aria-label={t('toggleLocale')}
    >
      <Languages className="h-4 w-4" />
      <span>{locale === 'zh' ? 'EN' : '中'}</span>
    </button>
  );
}
