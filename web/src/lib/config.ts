import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { load } from 'js-yaml';
import { SkillsFileSchema, type Skill, type SkillsFile } from './types';

const CONFIG_PATH = resolve(process.cwd(), 'data/skills.yml');

/** Load and validate skills.yml at build time. */
export function loadSkillsData(): SkillsFile {
  const raw = readFileSync(CONFIG_PATH, 'utf-8');
  const parsed = load(raw);
  return SkillsFileSchema.parse(parsed);
}

export function getSkillById(id: string): Skill | undefined {
  const data = loadSkillsData();
  return data.skills.find((skill) => skill.id === id);
}
