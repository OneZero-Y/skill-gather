import { ArrowRight } from 'lucide-react';
import type { Skill } from '@/lib/types';
import { cn } from '@/lib/utils';
import { SkillCard } from './SkillCard';
import { SkillList } from './SkillList';

interface SkillSectionProps {
  title: string;
  skills: Skill[];
  viewAllLabel?: string;
  viewAllHref?: string;
  layout?: 'row' | 'list';
  className?: string;
}

export function SkillSection({
  title,
  skills,
  viewAllLabel,
  viewAllHref,
  layout = 'row',
  className,
}: SkillSectionProps) {
  if (skills.length === 0) return null;

  return (
    <section className={className}>
      {/* Section header */}
      <div className="mb-5 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          {/* Accent bar */}
          <span className="h-5 w-1 rounded-full bg-accent" aria-hidden="true" />
          <h2 className="font-display text-lg font-semibold md:text-xl">{title}</h2>
        </div>
        {viewAllLabel && viewAllHref && (
          <a
            href={viewAllHref}
            className="group inline-flex shrink-0 items-center gap-1 rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium text-muted transition hover:border-accent/30 hover:bg-card-hover hover:text-accent"
          >
            {viewAllLabel}
            <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
          </a>
        )}
      </div>

      {layout === 'list' ? (
        <SkillList skills={skills} />
      ) : (
        /* Horizontal scroll row with fade edges */
        <div className="relative">
          {/* Right fade hint */}
          <div
            className="pointer-events-none absolute right-0 top-0 z-10 h-full w-16 bg-gradient-to-l from-background to-transparent"
            aria-hidden="true"
          />
          <div className={cn(
            'chip-scroll -mx-4 flex gap-3 overflow-x-auto px-4 pb-2 md:mx-0 md:px-0',
          )}>
            {skills.map((skill, index) => (
              <SkillCard key={skill.id} skill={skill} index={index} variant="row" />
            ))}
            {/* Trailing spacer so last card isn't clipped by the fade */}
            <div className="w-4 shrink-0 md:hidden" aria-hidden="true" />
          </div>
        </div>
      )}
    </section>
  );
}
