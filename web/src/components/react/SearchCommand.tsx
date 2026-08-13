import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Command } from 'cmdk';
import { ExternalLink, Search, X } from 'lucide-react';
import MiniSearch from 'minisearch';
import type { Skill } from '@/lib/types';
import { cn, skillDetailPath } from '@/lib/utils';
import { useI18n } from './LocaleProvider';

interface SearchCommandProps {
  skills: Skill[];
  className?: string;
  variant?: 'default' | 'hero';
}

/** 构建 MiniSearch 索引（懒初始化，只建一次） */
function buildIndex(skills: Skill[]): MiniSearch<Skill> {
  const ms = new MiniSearch<Skill>({
    idField: 'id',
    fields: ['name', 'description', 'tags_str', 'source', 'zh_keywords'],
    storeFields: ['id', 'name', 'description', 'score', 'source'],
    searchOptions: {
      // 前缀匹配：输入 "doc" 可匹配 "docker"
      prefix: true,
      // 模糊匹配：允许 20% 编辑距离（如 "databse" → "database"）
      fuzzy: 0.2,
      // 各字段权重：name 最重要，中文关键词次之
      boost: { name: 3, zh_keywords: 2, description: 1, tags_str: 1.5 },
    },
  });

  // minisearch 需要扁平对象，tags 是数组要先转字符串
  const docs = skills.map((s) => ({
    ...s,
    tags_str: s.tags.join(' '),
    zh_keywords: s.zh_keywords ?? '',
  }));
  ms.addAll(docs);
  return ms;
}

export function SearchCommand({ skills, className, variant = 'default' }: SearchCommandProps) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  // 索引懒建：第一次打开时才初始化，之后复用
  const indexRef = useRef<MiniSearch<Skill> | null>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery('');
  }, []);

  // 打开时初始化索引（避免页面加载时阻塞）
  useEffect(() => {
    if (open && !indexRef.current) {
      indexRef.current = buildIndex(skills);
    }
  }, [open, skills]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen((v) => !v);
      }
      if (e.key === 'Escape') {
        close();
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [close]);

  const skillById = useMemo(() => {
    const map = new Map<string, Skill>();
    for (const s of skills) map.set(s.id, s);
    return map;
  }, [skills]);

  const filtered = useMemo(() => {
    const q = query.trim();
    if (!q) return skills.slice(0, 10);

    const index = indexRef.current;
    if (!index) {
      // 索引还未就绪，降级到 includes
      const ql = q.toLowerCase();
      return skills
        .filter(
          (s) =>
            s.name.toLowerCase().includes(ql) ||
            s.description.toLowerCase().includes(ql) ||
            (s.zh_keywords ? s.zh_keywords.includes(q) : false),
        )
        .slice(0, 50);
    }

    const results = index.search(q);
    return results
      .slice(0, 50)
      .map((r) => skillById.get(r.id))
      .filter((s): s is Skill => s !== undefined);
  }, [query, skills, skillById]);

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          'flex items-center gap-2 rounded-xl border border-border bg-card px-3',
          'text-sm text-muted transition-all hover:border-accent/30 hover:text-foreground',
          variant === 'hero'
            ? 'h-12 w-full shadow-sm'
            : 'h-10 w-full sm:max-w-md',
          className,
        )}
      >
        <Search className="h-4 w-4 shrink-0" />
        <span className="truncate">{t('searchPlaceholder')}</span>
        <kbd className="ml-auto hidden rounded-md bg-background px-1.5 py-0.5 text-[10px] ring-1 ring-border md:inline">
          ⌘K
        </kbd>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-background/70 p-4 pt-[12vh] backdrop-blur-sm">
      <Command
        className="glass w-full max-w-xl overflow-hidden rounded-2xl shadow-2xl"
        shouldFilter={false}
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="h-4 w-4 text-muted" />
          <Command.Input
            value={query}
            onValueChange={setQuery}
            placeholder={t('searchInputPlaceholder')}
            className="flex-1 bg-transparent py-3 text-sm outline-none"
            autoFocus
          />
          <button type="button" onClick={close} className="text-muted hover:text-foreground">
            <X className="h-4 w-4" />
          </button>
        </div>
        <Command.List className="max-h-80 overflow-y-auto p-2">
          {filtered.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-muted">{t('searchNoResults')}</div>
          ) : (
            filtered.map((skill) => (
              <Command.Item
                key={skill.id}
                value={skill.id}
                onSelect={() => {
                  window.location.href = skillDetailPath(skill.id);
                  close();
                }}
                className={cn(
                  'flex cursor-pointer items-start gap-3 rounded-xl px-3 py-2.5 text-sm outline-none',
                  'aria-selected:bg-accent/10',
                )}
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium">{skill.name}</div>
                  <div className="truncate text-xs text-muted">{skill.id}</div>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted">
                  <span>{skill.score}</span>
                  <ExternalLink className="h-3.5 w-3.5" />
                </div>
              </Command.Item>
            ))
          )}
        </Command.List>
      </Command>
    </div>
  );
}
