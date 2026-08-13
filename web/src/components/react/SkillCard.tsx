import { ArrowUpRight, Download, Star } from 'lucide-react';
import type { Skill } from '@/lib/types';
import { cn, formatNumber, skillDetailPath } from '@/lib/utils';

interface SkillCardProps {
  skill: Skill;
  index?: number;
  variant?: 'grid' | 'row';
}

// Per-platform colour tokens (Tailwind arbitrary values avoided — use preset classes)
const PLATFORM_STYLES: Record<string, string> = {
  claude_code: 'bg-orange-500/10 text-orange-400 ring-orange-500/20',
  claude_ai:   'bg-orange-500/10 text-orange-400 ring-orange-500/20',
  kiro:        'bg-violet-500/10 text-violet-400 ring-violet-500/20',
  codex:       'bg-green-500/10  text-green-400  ring-green-500/20',
  universal:   'bg-sky-500/10    text-sky-400    ring-sky-500/20',
};

const PLATFORM_SHORT: Record<string, string> = {
  claude_code: 'Claude',
  claude_ai:   'Claude.ai',
  kiro:        'Kiro',
  codex:       'Codex',
  universal:   'Universal',
};

function ScoreBadge({ score }: { score: number }) {
  const colour =
    score >= 80 ? 'bg-green-500/15 text-green-400 ring-green-500/25' :
    score >= 60 ? 'bg-accent/15 text-accent ring-accent/25' :
                  'bg-muted/15 text-muted ring-border';
  return (
    <span className={cn('shrink-0 rounded-lg px-2 py-1 text-xs font-bold ring-1', colour)}>
      {score}
    </span>
  );
}

export function SkillCard({ skill, index = 0, variant = 'grid' }: SkillCardProps) {
  const visiblePlatforms = skill.platforms.slice(0, 3);
  const extraCount = skill.platforms.length - visiblePlatforms.length;

  return (
    <a
      href={skillDetailPath(skill.id)}
      className={cn(
        'group relative flex flex-col rounded-2xl border border-border bg-card',
        'transition-all duration-300 hover:-translate-y-0.5 hover:border-accent/35',
        'hover:bg-card-hover hover:shadow-xl hover:shadow-accent/8',
        variant === 'grid' && 'animate-fade-up p-4 gap-3',
        variant === 'row' && 'w-[300px] shrink-0 p-4 gap-3 sm:w-[320px]',
      )}
      style={variant === 'grid' ? { animationDelay: `${index * 35}ms` } : undefined}
    >
      {/* Top row: name + score */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <h3 className="truncate font-semibold text-foreground">{skill.name}</h3>
            <ArrowUpRight
              className="h-3.5 w-3.5 shrink-0 text-muted opacity-0 transition-all group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-accent group-hover:opacity-100"
              aria-hidden="true"
            />
          </div>
          <p className="mt-0.5 truncate text-[11px] text-muted/70">{skill.source}</p>
        </div>
        <ScoreBadge score={skill.score} />
      </div>

      {/* Description */}
      <p className="line-clamp-2 flex-1 text-xs leading-relaxed text-muted">{skill.description}</p>

      {/* Bottom row: signals + platforms */}
      <div className="flex items-center gap-2 text-[11px]">
        {/* Stars */}
        {skill.stars > 0 && (
          <span className="inline-flex items-center gap-0.5 rounded-md bg-background px-1.5 py-0.5 text-muted ring-1 ring-border">
            <Star className="h-2.5 w-2.5 text-yellow-400" />
            {formatNumber(skill.stars)}
          </span>
        )}
        {/* Installs */}
        {skill.installs > 0 && (
          <span className="inline-flex items-center gap-0.5 rounded-md bg-background px-1.5 py-0.5 text-muted ring-1 ring-border">
            <Download className="h-2.5 w-2.5" />
            {formatNumber(skill.installs)}
          </span>
        )}

        {/* Spacer */}
        <div className="flex-1" />

        {/* Platform badges */}
        <div className="flex items-center gap-1">
          {visiblePlatforms.map((p) => (
            <span
              key={p}
              title={PLATFORM_SHORT[p] ?? p}
              className={cn(
                'rounded-md px-1.5 py-0.5 ring-1',
                PLATFORM_STYLES[p] ?? 'bg-muted/10 text-muted ring-border',
              )}
            >
              {PLATFORM_SHORT[p] ?? p}
            </span>
          ))}
          {extraCount > 0 && (
            <span className="rounded-md bg-background px-1.5 py-0.5 text-muted ring-1 ring-border">
              +{extraCount}
            </span>
          )}
        </div>
      </div>

      {/* Accent underline on hover */}
      <div
        className="absolute inset-x-4 -bottom-px h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent scale-x-0 transition-transform duration-300 group-hover:scale-x-100"
        aria-hidden="true"
      />
    </a>
  );
}
