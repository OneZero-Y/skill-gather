import { ArrowUpRight, Star } from 'lucide-react';
import type { Skill } from '@/lib/types';
import { PLATFORM_LABELS } from '@/lib/types';
import { cn, formatNumber, skillDetailPath } from '@/lib/utils';

interface SkillCardProps {
  skill: Skill;
  index?: number;
}

export function SkillCard({ skill, index = 0 }: SkillCardProps) {
  return (
    <a
      href={skillDetailPath(skill.id)}
      className={cn(
        'group relative flex flex-col gap-3 rounded-2xl border border-border bg-card p-4',
        'transition-all duration-300 hover:-translate-y-0.5 hover:border-accent/40',
        'hover:bg-card-hover hover:shadow-lg hover:shadow-accent/5',
        'animate-fade-up',
      )}
      style={{ animationDelay: `${index * 35}ms` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h3 className="truncate font-medium text-foreground">{skill.name}</h3>
            <ArrowUpRight
              className={cn(
                'h-3.5 w-3.5 shrink-0 text-muted opacity-0 transition-all',
                'group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-accent group-hover:opacity-100',
              )}
            />
          </div>
          <p className="mt-0.5 truncate text-xs text-muted">{skill.id}</p>
        </div>
        <span className="shrink-0 rounded-lg bg-accent/10 px-2 py-1 text-xs font-semibold text-accent">
          {skill.score}
        </span>
      </div>

      <p className="line-clamp-2 text-xs leading-relaxed text-muted">{skill.description}</p>

      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
        {skill.stars > 0 && (
          <span className="inline-flex items-center gap-0.5 rounded-md bg-background px-1.5 py-0.5 ring-1 ring-border">
            <Star className="h-3 w-3 text-warm" />
            {formatNumber(skill.stars)}
          </span>
        )}
        <span className="rounded-md bg-background px-1.5 py-0.5 ring-1 ring-border">{skill.source}</span>
        {skill.platforms.slice(0, 3).map((p) => (
          <span key={p} className="rounded-md bg-background px-1.5 py-0.5 ring-1 ring-border">
            {PLATFORM_LABELS[p] ?? p}
          </span>
        ))}
      </div>
    </a>
  );
}
