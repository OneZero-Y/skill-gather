import { Star } from 'lucide-react';
import type { Skill } from '@/lib/types';
import { getCategoryIcon } from '@/lib/category-icons';
import { cn, formatNumber, skillDetailPath } from '@/lib/utils';
import { useI18n } from './LocaleProvider';

interface SkillListProps {
  skills: Skill[];
  /** 1-based rank for first item */
  startRank?: number;
  showRank?: boolean;
  className?: string;
}

export function SkillList({ skills, startRank = 1, showRank = true, className }: SkillListProps) {
  if (skills.length === 0) return null;

  return (
    <div className={cn('overflow-hidden rounded-xl border border-border bg-card', className)}>
      {skills.map((skill, index) => (
        <SkillListItem
          key={skill.id}
          skill={skill}
          rank={showRank ? startRank + index : undefined}
        />
      ))}
    </div>
  );
}

function SkillListItem({ skill, rank }: { skill: Skill; rank?: number }) {
  const { categoryLabel } = useI18n();
  const Icon = getCategoryIcon(skill.category);

  return (
    <a
      href={skillDetailPath(skill.id)}
      className={cn(
        'group flex items-center gap-3 border-b border-border px-3 py-3 transition last:border-b-0',
        'hover:bg-card-hover sm:gap-4 sm:px-4',
      )}
    >
      {rank != null && (
        <span className="w-6 shrink-0 font-mono text-xs tabular-nums text-muted">
          {String(rank).padStart(2, '0')}
        </span>
      )}

      <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-accent/10 text-accent">
        <Icon className="h-4 w-4" />
      </span>

      <span className="min-w-0 flex-1 truncate text-sm font-medium text-foreground group-hover:text-accent">
        {skill.name}
      </span>

      <span className="hidden shrink-0 border border-border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted sm:inline">
        {categoryLabel(skill.category)}
      </span>

      {skill.stars > 0 ? (
        <span className="inline-flex shrink-0 items-center gap-1 font-mono text-xs text-muted">
          <Star className="h-3.5 w-3.5 text-warm" />
          {formatNumber(skill.stars)}
        </span>
      ) : (
        <span className="shrink-0 font-mono text-xs text-accent">{skill.score}</span>
      )}
    </a>
  );
}
