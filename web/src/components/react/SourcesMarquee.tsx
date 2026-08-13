/**
 * SourcesMarquee — infinite scroll strip showing all data source names.
 * Renders two identical rows scrolling in opposite directions for depth.
 */
import { cn } from '@/lib/utils';

interface SourcesMarqueeProps {
  sources: { id: string; count: number }[];
}

// Human-readable labels + optional icon emoji for each source
const SOURCE_META: Record<string, { label: string; emoji: string; tier: 'official' | 'community' }> = {
  'anthropics-skills':           { label: 'Anthropic',       emoji: '🤖', tier: 'official' },
  'openai-skills':               { label: 'OpenAI',          emoji: '⚡', tier: 'official' },
  'vercel-agent-skills':         { label: 'Vercel',          emoji: '▲',  tier: 'official' },
  'langchain-skills':            { label: 'LangChain',       emoji: '🦜', tier: 'official' },
  'aws-agent-toolkit':           { label: 'AWS',             emoji: '☁️', tier: 'official' },
  'github-awesome-copilot':      { label: 'GitHub',          emoji: '🐙', tier: 'official' },
  'microsoft-vscode-skills':     { label: 'Microsoft',       emoji: '🪟', tier: 'official' },
  'supabase-skills':             { label: 'Supabase',        emoji: '⚡', tier: 'official' },
  'bytedance-deerflow':          { label: 'ByteDance',       emoji: '🦋', tier: 'official' },
  'scientific-agent-skills':     { label: 'K-Dense AI',      emoji: '🔬', tier: 'community' },
  'orchestra-ai-research-skills':{ label: 'Orchestra Research', emoji: '🎻', tier: 'community' },
  'voltagent-awesome':           { label: 'VoltAgent',       emoji: '⚡', tier: 'community' },
  'voltagent-awesome-claude':    { label: 'Awesome Claude',  emoji: '✨', tier: 'community' },
  'heilcheng-awesome':           { label: 'Awesome Skills',  emoji: '🌟', tier: 'community' },
  'community-repos':             { label: 'Community',       emoji: '🌍', tier: 'community' },
  'skillhub-cn':                 { label: 'SkillHub CN',     emoji: '🇨🇳', tier: 'community' },
  'mcpmarket-cn':                { label: 'MCP Market',      emoji: '🏪', tier: 'community' },
  'skills-sh-signals':           { label: 'skills.sh',      emoji: '📊', tier: 'community' },
};

function SourceBadge({ id, count }: { id: string; count: number }) {
  const meta = SOURCE_META[id] ?? { label: id, emoji: '📦', tier: 'community' };
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium',
        'transition-colors select-none',
        meta.tier === 'official'
          ? 'border-accent/25 bg-accent/8 text-accent hover:bg-accent/15'
          : 'border-border bg-card text-muted hover:border-accent/20 hover:text-foreground',
      )}
    >
      <span aria-hidden="true">{meta.emoji}</span>
      <span>{meta.label}</span>
      <span className="rounded-full bg-background/60 px-1.5 py-0.5 text-xs font-mono">
        {count}
      </span>
    </span>
  );
}

export function SourcesMarquee({ sources }: SourcesMarqueeProps) {
  if (sources.length === 0) return null;

  // Filter out signal-only sources (skills-sh-signals never has skills)
  const visible = sources.filter((s) => s.count > 0 && s.id !== 'skills-sh-signals');

  // Split into two rows for the two-track effect
  const half = Math.ceil(visible.length / 2);
  const row1 = visible.slice(0, half);
  const row2 = visible.slice(half);

  return (
    <section className="relative overflow-hidden border-y border-border/50 bg-background/50 py-5" aria-label="Data sources">
      {/* Edge fades */}
      <div className="pointer-events-none absolute inset-y-0 left-0 z-10 w-20 bg-gradient-to-r from-background to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 z-10 w-20 bg-gradient-to-l from-background to-transparent" />

      <div className="space-y-3">
        {/* Row 1 — scrolls left */}
        <div className="flex animate-marquee-left gap-3 will-change-transform">
          {[...row1, ...row1].map((s, i) => (
            <SourceBadge key={`r1-${i}`} id={s.id} count={s.count} />
          ))}
        </div>

        {/* Row 2 — scrolls right */}
        {row2.length > 0 && (
          <div className="flex animate-marquee-right gap-3 will-change-transform">
            {[...row2, ...row2].map((s, i) => (
              <SourceBadge key={`r2-${i}`} id={s.id} count={s.count} />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
