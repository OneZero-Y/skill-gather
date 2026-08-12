import { ChevronRight } from 'lucide-react';
import type { Skill } from '@/lib/types';
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
      <div className="mb-4 flex items-end justify-between gap-3">
        <h2 className="font-display text-lg font-semibold md:text-xl">{title}</h2>
        {viewAllLabel && viewAllHref && (
          <a
            href={viewAllHref}
            className="inline-flex shrink-0 items-center gap-0.5 text-xs font-medium text-muted transition hover:text-accent"
          >
            {viewAllLabel}
            <ChevronRight className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      {layout === 'list' ? (
        <SkillList skills={skills} />
      ) : (
        <div className="chip-scroll -mx-4 flex gap-3 overflow-x-auto px-4 pb-1 md:mx-0 md:px-0">
          {skills.map((skill, index) => (
            <SkillCard key={skill.id} skill={skill} index={index} variant="row" />
          ))}
        </div>
      )}
    </section>
  );
}
