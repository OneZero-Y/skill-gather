import { z } from 'zod';

export const SkillSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  category: z.string(),
  score: z.number(),
  tags: z.array(z.string()),
  source: z.string(),
  install_url: z.string(),
  stars: z.number(),
  installs: z.number(),
  platforms: z.array(z.string()),
  license: z.string().optional().default(''),
});

export const CategorySchema = z.object({
  id: z.string(),
  name: z.string(),
  count: z.number(),
});

export const SourceSchema = z.object({
  id: z.string(),
  count: z.number(),
});

export const ChangelogSchema = z.object({
  added: z.number(),
  removed: z.number(),
  modified: z.number().optional(),
  total_old: z.number().optional(),
  total_new: z.number().optional(),
});

export const SkillsFileSchema = z.object({
  generated_at: z.string(),
  total: z.number(),
  site: z.object({
    title: z.string(),
    description: z.string().optional(),
  }),
  meta: z
    .object({
      last_synced: z.string().nullable().optional(),
      sources_count: z.number().optional(),
      changelog: ChangelogSchema.nullable().optional(),
    })
    .optional(),
  categories: z.array(CategorySchema),
  sources: z.array(SourceSchema),
  featured: z.array(SkillSchema),
  skills: z.array(SkillSchema),
});

export type Skill = z.infer<typeof SkillSchema>;
export type SkillsFile = z.infer<typeof SkillsFileSchema>;
export type Changelog = z.infer<typeof ChangelogSchema>;

export const PLATFORM_LABELS: Record<string, string> = {
  claude_code: 'Claude Code',
  claude_ai: 'Claude.ai',
  kiro: 'Kiro',
  codex: 'Codex',
  universal: 'Universal',
};
