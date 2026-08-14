---
name: skill-gather
description: >
  Search and install AI agent skills from a bundled registry of 11,000+ skills
  aggregated from GitHub, SkillHub, MCP Market and other sources. Use when the user
  wants to find a skill for a task, browse skills by category or platform, check what
  skills exist for Claude Code / Kiro / Cursor / Codex, or install a skill locally.
  Works offline from a bundled snapshot; refreshes from upstream when a GitHub token
  is configured.
allowed-tools:
  - Bash
license: MIT
compatibility: "Claude Code, Kiro, Cursor, Codex. Requires Python 3.12+. Installing skills additionally requires git."
---

# Skill Gather

Search and install AI agent skills from an index of 11,000+ skills gathered from GitHub,
SkillHub, MCP Market and community lists.

The registry ships with this skill as a snapshot, so search works with no network access
and no setup beyond a one-time dependency install.

## Running commands

All commands go through a single cross-platform entry point. Run them from this skill's
own directory (the directory containing this `SKILL.md`):

```
python bin/skill_gather_cli.py <command> [options]
```

Use `python3` instead of `python` on systems where `python` is not on PATH.

The wrapper resolves its own location, so the command works regardless of the caller's
working directory. Use an absolute path to the wrapper when the working directory is not
this skill's folder:

```
python /absolute/path/to/skill-gather/bin/skill_gather_cli.py search "excel"
```

## First run

Run `doctor` once before anything else. It reports whether dependencies are installed,
how large the bundled snapshot is, and whether a GitHub token and `git` are available.
It changes nothing.

```
python bin/skill_gather_cli.py doctor
```

Dependencies install automatically on the first real command (via `uv` if present,
otherwise `venv` + `pip`). This takes up to a minute once, then never again.

## Commands

### search — find skills by keyword

```
python bin/skill_gather_cli.py search "excel spreadsheet" --limit 10
python bin/skill_gather_cli.py search "docker" --category devops --min-score 60
python bin/skill_gather_cli.py search "code review" --platform claude_code
```

Options: `--limit N`, `--category <name>`, `--platform <name>`, `--source <id>`,
`--min-score N`.

Higher scores mean better-documented, more widely adopted skills. Scores above 60 are
strong; most entries fall between 25 and 50.

### show — full detail for one skill

```
python bin/skill_gather_cli.py show anthropics/skills/mcp-builder
python bin/skill_gather_cli.py show xlsx
```

Accepts a partial id. When several skills match, candidates are listed instead of
picking one arbitrarily. Add `--json` for machine-readable output.

### list — browse by facet

```
python bin/skill_gather_cli.py list --category development --limit 20
python bin/skill_gather_cli.py list --platform kiro --min-score 50
python bin/skill_gather_cli.py list --source anthropics-skills
```

Categories: `development`, `devops`, `document`, `data`, `security`, `creative`,
`productivity`, `education`, `ecommerce`, `content`, `other`.

Platforms: `claude_code`, `claude_ai`, `kiro`, `codex`, `universal`.

### install — install a skill locally

Requires `git`. Pick the preset matching the user's agent:

```
python bin/skill_gather_cli.py install <skill_id> --preset claude
python bin/skill_gather_cli.py install <skill_id> --preset kiro
python bin/skill_gather_cli.py install <skill_id> --preset cursor
```

Install into the current project instead of the user's home directory:

```
python bin/skill_gather_cli.py install <skill_id> --target ./.claude/skills
```

Add `--force` to overwrite an existing installation.

Confirm the target with the user before installing, since this writes into their agent
configuration.

### update — refresh the registry

```
python bin/skill_gather_cli.py update
```

Requires a GitHub token. Without one this reports the snapshot age and exits successfully
without changing anything — anonymous GitHub access is capped at 60 requests/hour, which
is not enough to complete a sync, and a partial sync would be worse than the snapshot.

To enable updates, set a token with public repository read access:

- macOS / Linux: `export GITHUB_TOKEN=ghp_xxxx`
- Windows PowerShell: `$env:GITHUB_TOKEN = "ghp_xxxx"`
- Windows cmd: `set GITHUB_TOKEN=ghp_xxxx`

Tokens are created at https://github.com/settings/tokens. A sync across all sources takes
several minutes. If it fails, the previous snapshot stays in place and search keeps working.

### stats — registry overview

```
python bin/skill_gather_cli.py stats
```

## Recommended workflow

When the user asks for a skill to accomplish something:

1. `search` with keywords from their request, `--limit 5`.
2. Present the top matches with name, score and one-line description. Do not dump raw
   output — summarise it.
3. If nothing relevant comes back, retry with broader or alternative terms (both English
   and the user's own language; the index covers Chinese-language skills too) before
   concluding none exists.
4. Once the user picks one, run `show` to get its details and source URL.
5. Ask which agent to install into, then `install` with the matching `--preset`.

## Notes

- Registry data is a snapshot taken when this skill was published. Run `doctor` to see
  its date.
- Search is local and offline. Only `update` and `install` need network access.
- Skill content is not bundled: this is an index. `install` fetches the real files from
  the upstream repository.
