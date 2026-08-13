/** Official skill-gather repository — used in install instructions */
export const SKILL_STORE_GITHUB = 'https://github.com/OneZero-Y/skill-gather';


export interface InstallPreset {
  id: string;
  label: { zh: string; en: string };
  path: string;
  /** CLI args after `skill-gather install <id>` */
  args: string;
}

export const INSTALL_PRESETS: InstallPreset[] = [
  {
    id: 'cursor',
    label: { zh: 'Cursor', en: 'Cursor' },
    path: '~/.cursor/skills',
    args: '--preset cursor',
  },
  {
    id: 'claude',
    label: { zh: 'Claude Code', en: 'Claude Code' },
    path: '~/.claude/skills',
    args: '--preset claude',
  },
  {
    id: 'kiro',
    label: { zh: 'Kiro', en: 'Kiro' },
    path: '~/.kiro/skills',
    args: '--preset kiro',
  },
  {
    id: 'openclaw',
    label: { zh: 'OpenClaw / Claw', en: 'OpenClaw / Claw' },
    path: '~/.openclaw/skills',
    args: '--preset openclaw',
  },
  {
    id: 'hermes',
    label: { zh: 'Hermes', en: 'Hermes' },
    path: '~/.hermes/skills',
    args: '--preset hermes',
  },
  {
    id: 'project-cursor',
    label: { zh: 'Cursor（项目）', en: 'Cursor (project)' },
    path: './.cursor/skills',
    args: '--preset project-cursor',
  },
];

export function buildInstallCommand(skillId: string, preset: InstallPreset): string {
  return `skill-gather install ${skillId} ${preset.args}`.trim();
}
