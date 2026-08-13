/**
 * SourceGrid — shows all data sources as cards with skill counts.
 * Clicking a card jumps to /skills/all?source=<id>
 */
import { ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';
import { browseAllPath } from '@/lib/utils';

interface SourceGridProps {
  sources: { id: string; count: number }[];
  title?: string;
  viewAllLabel?: string;
}

// Full metadata for source display
const SOURCE_META: Record<string, {
  label: string;
  emoji: string;
  description: string;
  tier: 'official' | 'community';
  color: string;  // Tailwind classes for the accent strip
}> = {
  'anthropics-skills': {
    label: 'Anthropic', emoji: '🤖',
    description: 'Official skills from Anthropic: docx, pptx, pdf, mcp-builder, webapp-testing…',
    tier: 'official',
    color: 'from-orange-500/20 to-orange-500/5',
  },
  'openai-skills': {
    label: 'OpenAI', emoji: '⚡',
    description: 'Official OpenAI / Codex agent skills',
    tier: 'official',
    color: 'from-green-500/20 to-green-500/5',
  },
  'vercel-agent-skills': {
    label: 'Vercel', emoji: '▲',
    description: 'Vercel official skills: deploy, react, nextjs, web-design-guidelines…',
    tier: 'official',
    color: 'from-sky-500/20 to-sky-500/5',
  },
  'langchain-skills': {
    label: 'LangChain', emoji: '🦜',
    description: 'LangChain / LangGraph / Deep Agents skills for building AI applications',
    tier: 'official',
    color: 'from-violet-500/20 to-violet-500/5',
  },
  'aws-agent-toolkit': {
    label: 'Amazon AWS', emoji: '☁️',
    description: 'AWS official toolkit: iam, cdk, auth, networking, ai-ml, rds…',
    tier: 'official',
    color: 'from-yellow-500/20 to-yellow-500/5',
  },
  'github-awesome-copilot': {
    label: 'GitHub Copilot', emoji: '🐙',
    description: 'GitHub official: refactor, code-review, git-flow, draw.io diagrams…',
    tier: 'official',
    color: 'from-slate-500/20 to-slate-500/5',
  },
  'microsoft-vscode-skills': {
    label: 'Microsoft VSCode', emoji: '🪟',
    description: 'VS Code built-in skills: commit, fix-ci, code-review, merge, troubleshoot',
    tier: 'official',
    color: 'from-blue-500/20 to-blue-500/5',
  },
  'supabase-skills': {
    label: 'Supabase', emoji: '⚡',
    description: 'Supabase internal skills: error handling, react-hook-form, copywriting…',
    tier: 'official',
    color: 'from-emerald-500/20 to-emerald-500/5',
  },
  'bytedance-deerflow': {
    label: 'ByteDance DeerFlow', emoji: '🦋',
    description: 'ByteDance DeerFlow framework: data analysis, video generation, deep research…',
    tier: 'official',
    color: 'from-pink-500/20 to-pink-500/5',
  },
  'scientific-agent-skills': {
    label: 'K-Dense AI Science', emoji: '🔬',
    description: '158 scientific skills: biology, chemistry, medicine, drug discovery…',
    tier: 'community',
    color: 'from-teal-500/20 to-teal-500/5',
  },
  'orchestra-ai-research-skills': {
    label: 'Orchestra Research', emoji: '🎻',
    description: 'AI research engineering skills: RAG, FAISS, Qdrant, evaluation…',
    tier: 'community',
    color: 'from-purple-500/20 to-purple-500/5',
  },
  'voltagent-awesome': {
    label: 'VoltAgent Awesome', emoji: '⚡',
    description: 'Curated awesome-list of 160+ agent skill repos from the community',
    tier: 'community',
    color: 'from-amber-500/20 to-amber-500/5',
  },
  'voltagent-awesome-claude': {
    label: 'Awesome Claude Skills', emoji: '✨',
    description: 'Large community-curated list of 1000+ Claude-compatible skills',
    tier: 'community',
    color: 'from-amber-500/20 to-amber-500/5',
  },
  'community-repos': {
    label: 'Community Repos', emoji: '🌍',
    description: 'Curated individual repos: Terraform, Cypress, Snyk, Angular, NVIDIA…',
    tier: 'community',
    color: 'from-cyan-500/20 to-cyan-500/5',
  },
  'skillhub-cn': {
    label: 'SkillHub CN', emoji: '🇨🇳',
    description: 'Chinese skills community platform (Tencent) — pending integration',
    tier: 'community',
    color: 'from-red-500/20 to-red-500/5',
  },
  'mcpmarket-cn': {
    label: 'MCP Market CN', emoji: '🏪',
    description: 'MCP Market Chinese platform — pending integration',
    tier: 'community',
    color: 'from-rose-500/20 to-rose-500/5',
  },
};

function SourceCard({ id, count }: { id: string; count: number }) {
  const meta = SOURCE_META[id] ?? {
    label: id,
    emoji: '📦',
    description: `${count} skills from this source`,
    tier: 'community' as const,
    color: 'from-muted/20 to-muted/5',
  };

  const isPending = count === 0;

  return (
    <a
      href={isPending ? undefined : browseAllPath({ source: id })}
      className={cn(
        'group relative flex flex-col gap-3 overflow-hidden rounded-2xl border border-border bg-card p-4',
        'transition-all duration-300',
        isPending
          ? 'cursor-default opacity-60'
          : 'hover:-translate-y-0.5 hover:border-accent/30 hover:bg-card-hover hover:shadow-lg hover:shadow-accent/8',
      )}
      aria-disabled={isPending}
    >
      {/* Gradient top strip */}
      <div className={cn('absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r', meta.color)} />

      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-xl" aria-hidden="true">{meta.emoji}</span>
          <span className="font-semibold text-foreground">{meta.label}</span>
          {meta.tier === 'official' && (
            <span className="rounded-full bg-accent/10 px-1.5 py-0.5 text-[10px] font-medium text-accent ring-1 ring-accent/20">
              Official
            </span>
          )}
        </div>
        {!isPending && (
          <ArrowRight
            className="h-4 w-4 shrink-0 text-muted opacity-0 transition-all group-hover:translate-x-0.5 group-hover:text-accent group-hover:opacity-100"
            aria-hidden="true"
          />
        )}
      </div>

      {/* Description */}
      <p className="line-clamp-2 flex-1 text-xs leading-relaxed text-muted">
        {isPending ? '🔧 Integration in progress — coming soon' : meta.description}
      </p>

      {/* Footer: skill count */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted">
          {isPending ? 'Pending' : `${count.toLocaleString()} skills`}
        </span>
        {!isPending && (
          <span className="font-medium text-accent opacity-0 transition-opacity group-hover:opacity-100">
            Browse →
          </span>
        )}
      </div>
    </a>
  );
}

export function SourceGrid({ sources, title }: SourceGridProps) {
  if (sources.length === 0) return null;

  const official = sources.filter((s) => {
    const meta = SOURCE_META[s.id];
    return meta?.tier === 'official';
  });
  const community = sources.filter((s) => {
    const meta = SOURCE_META[s.id];
    return meta?.tier === 'community' || !meta;
  });

  return (
    <section id="sources" className="scroll-mt-20">
      {/* Section header */}
      <div className="mb-6 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="h-5 w-1 rounded-full bg-accent" aria-hidden="true" />
          <h2 className="font-display text-lg font-semibold md:text-xl">
            {title ?? 'Data Sources'}
          </h2>
        </div>
        <span className="text-xs text-muted">{sources.length} sources</span>
      </div>

      {/* Official sources */}
      {official.length > 0 && (
        <div className="mb-6">
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted">
            Official Organisations
          </p>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
            {official.map((s) => (
              <SourceCard key={s.id} id={s.id} count={s.count} />
            ))}
          </div>
        </div>
      )}

      {/* Community sources */}
      {community.length > 0 && (
        <div>
          <p className="mb-3 text-xs font-medium uppercase tracking-wider text-muted">
            Community & Aggregators
          </p>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
            {community.map((s) => (
              <SourceCard key={s.id} id={s.id} count={s.count} />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
