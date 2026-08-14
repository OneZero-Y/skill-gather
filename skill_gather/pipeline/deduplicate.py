"""Deduplicate skills that appear in multiple sources.

Two passes, because a single key cannot catch both duplicate shapes:

  Pass 1 — location key: normalized install URL / repo+path. Catches entries
           that point at literally the same place.

  Pass 2 — content key: normalized "owner/repo" + skill name, ignoring the
           in-repo path. This is the pass that actually matters. Different
           sources guess different paths for the same skill (mcpmarket-cn
           hardcodes `skills/<name>`, while the real location may be
           `.claude/skills/<name>` or `config/skills/<name>`), so the location
           key never collides even though it is the same skill.

When a group is merged we keep the richest entry, take the strongest signal
from each field, and record which other sources had it — cross-source presence
becomes a trust signal that does not depend on the GitHub API being reachable.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from skill_gather.models import SkillIndex

logger = logging.getLogger(__name__)


@dataclass
class DedupStats:
    """Observable outcome of the dedup pass (surfaced in registry meta.json)."""

    input_count: int = 0
    output_count: int = 0
    removed_by_location: int = 0
    removed_by_content: int = 0
    disambiguated_ids: int = 0
    multi_source_skills: int = 0
    largest_group: int = 0
    largest_group_key: str = ""
    merged_source_pairs: dict[str, int] = field(default_factory=dict)

    @property
    def removed_count(self) -> int:
        return self.input_count - self.output_count

    @property
    def dedup_rate(self) -> float:
        if self.input_count <= 0:
            return 0.0
        return round(self.removed_count / self.input_count * 100, 2)

    def to_dict(self) -> dict:
        return {
            "input_count": self.input_count,
            "output_count": self.output_count,
            "removed_count": self.removed_count,
            "removed_by_location": self.removed_by_location,
            "removed_by_content": self.removed_by_content,
            "disambiguated_ids": self.disambiguated_ids,
            "dedup_rate_pct": self.dedup_rate,
            "multi_source_skills": self.multi_source_skills,
            "largest_group": self.largest_group,
            "largest_group_key": self.largest_group_key,
            "top_overlapping_source_pairs": dict(
                sorted(self.merged_source_pairs.items(), key=lambda kv: -kv[1])[:10]
            ),
        }


# ---------------------------------------------------------------------------
# Key builders
# ---------------------------------------------------------------------------

def _normalize_repo_url(url: str) -> str:
    """Normalize a repo URL to host/owner/repo form."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/").split("/tree/")[0].split("/blob/")[0]
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return f"{parsed.netloc.lower()}/{parts[0]}/{parts[1]}".lower()
    return f"{parsed.netloc.lower()}{path}".lower()


def _normalize_skill_location(url: str) -> str:
    """Normalize a skill URL while preserving its path within the repo."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) >= 4 and parts[2] in ("tree", "blob"):
        owner, repo = parts[0], parts[1]
        rest = parts[4:]
        if rest:
            return f"{parsed.netloc.lower()}/{owner}/{repo}/{'/'.join(rest)}".lower()
    return _normalize_repo_url(url)


def _location_key(skill: SkillIndex) -> str:
    """Pass 1 key: where this skill physically lives."""
    install_url = skill.discovery.install_url.strip()
    if install_url:
        return _normalize_skill_location(install_url)
    if skill.discovery.source_path:
        base = _normalize_repo_url(skill.discovery.source_url)
        return f"{base}/{skill.discovery.source_path}".lower()
    return skill.skill_id.lower()


def _canonical_name(name: str) -> str:
    """Collapse naming variants so 'code-review', 'code_review', 'CodeReview' match."""
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _content_key(skill: SkillIndex) -> str | None:
    """Pass 2 key: repo + skill name, path-independent.

    Returns None when there is no repo to anchor on — platform-only entries
    (e.g. a SkillHub-hosted skill with no GitHub upstream) are left alone,
    because matching those on name alone would merge unrelated skills.
    """
    repo = skill.discovery.repo.strip().lower()
    if not repo:
        return None
    name = _canonical_name(skill.spec.name)
    if not name:
        return None
    return f"{repo}#{name}"


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------

def _richness_score(skill: SkillIndex) -> int:
    """Score how rich/complete a skill entry is (higher = better to keep)."""
    score = 0
    if skill.spec.description:
        score += len(skill.spec.description[:200])
    if skill.spec.license:
        score += 20
    if skill.signals.has_scripts:
        score += 30
    if skill.signals.has_references:
        score += 20
    if skill.signals.file_count > 1:
        score += skill.signals.file_count * 5
    if skill.signals.repo_stars > 0:
        score += 10
    if skill.spec.compatibility:
        score += 15
    # Prefer an entry that already knows its real in-repo path over one that
    # guessed it, since that entry's install_url is the trustworthy one.
    if skill.discovery.source_path:
        score += 25
    return score


def _merge_group(group: list[SkillIndex], stats: DedupStats, key: str) -> SkillIndex:
    """Collapse a duplicate group into the single richest entry."""
    best = max(group, key=_richness_score)

    # Take the strongest available value for each independent signal.
    best.signals.repo_stars = max(s.signals.repo_stars for s in group)
    best.signals.install_count = max(s.signals.install_count for s in group)
    best.signals.file_count = max(s.signals.file_count for s in group)
    best.signals.has_scripts = any(s.signals.has_scripts for s in group)
    best.signals.has_references = any(s.signals.has_references for s in group)

    commit_dates = [s.signals.last_commit_date for s in group if s.signals.last_commit_date]
    if commit_dates:
        best.signals.last_commit_date = max(commit_dates)

    # Fill gaps in the spec from whichever sibling has the field.
    if not best.spec.description:
        for s in group:
            if s.spec.description:
                best.spec.description = s.spec.description
                break
    if not best.spec.license:
        for s in group:
            if s.spec.license:
                best.spec.license = s.spec.license
                break
    if not best.discovery.repo:
        for s in group:
            if s.discovery.repo:
                best.discovery.repo = s.discovery.repo
                break

    # Union of platform compatibility across all copies.
    for flag in ("claude_code", "claude_ai", "kiro", "codex", "universal"):
        if any(getattr(s.platform, flag) for s in group):
            setattr(best.platform, flag, True)

    # Record cross-source provenance.
    all_sources = {s.discovery.source_id for s in group}
    others = sorted(all_sources - {best.discovery.source_id})
    best.discovery.alternate_sources = sorted(
        set(best.discovery.alternate_sources) | set(others)
    )
    best.signals.source_count = max(
        len(all_sources),
        max(s.signals.source_count for s in group),
    )

    if best.signals.source_count > 1:
        stats.multi_source_skills += 1
        for pair in _source_pairs(all_sources):
            stats.merged_source_pairs[pair] = stats.merged_source_pairs.get(pair, 0) + 1

    if len(group) > stats.largest_group:
        stats.largest_group = len(group)
        stats.largest_group_key = key

    return best


def _source_pairs(sources: set[str]) -> list[str]:
    ordered = sorted(sources)
    return [
        f"{a}+{b}"
        for i, a in enumerate(ordered)
        for b in ordered[i + 1:]
    ]


def _collapse(
    skills: list[SkillIndex],
    key_fn,
    stats: DedupStats,
) -> tuple[list[SkillIndex], int]:
    """Group by key_fn and merge each group. Entries keyed None pass through."""
    groups: dict[str, list[SkillIndex]] = {}
    passthrough: list[SkillIndex] = []

    for skill in skills:
        key = key_fn(skill)
        if key is None:
            passthrough.append(skill)
            continue
        groups.setdefault(key, []).append(skill)

    result: list[SkillIndex] = []
    removed = 0
    for key, group in groups.items():
        if len(group) == 1:
            result.append(group[0])
            continue
        removed += len(group) - 1
        result.append(_merge_group(group, stats, key))

    result.extend(passthrough)
    return result, removed


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _enforce_unique_ids(skills: list[SkillIndex], stats: DedupStats) -> None:
    """Guarantee skill_id is unique, disambiguating collisions in place.

    skill_id is the registry's primary key: the writer, the diff and the MCP
    server all index by it. Collisions were silently swallowed by dict
    construction, so 11,334 records collapsed to 10,788 keys and `get_skill(id)`
    returned an arbitrary one of the colliding entries.

    Entries reaching this point already survived location and content dedup, so
    they are genuinely different skills that merely collide on a coarse id
    (e.g. two SkillHub publishers both naming a skill `excel`, which yields
    `skillhub-cn/excel` for both). Merging would discard real content, so we
    disambiguate instead.

    The suffix is derived from the entry's own install_url, so an id stays
    stable across runs regardless of what other entries exist.
    """
    seen: dict[str, SkillIndex] = {}
    collisions: list[SkillIndex] = []

    # The richest entry of each colliding group keeps the clean id.
    for skill in sorted(skills, key=_richness_score, reverse=True):
        if skill.skill_id in seen:
            collisions.append(skill)
        else:
            seen[skill.skill_id] = skill

    for skill in collisions:
        discriminator = hashlib.sha1(
            (skill.discovery.install_url or skill.discovery.source_url or skill.spec.name)
            .encode("utf-8")
        ).hexdigest()[:6]
        candidate = f"{skill.skill_id}~{discriminator}"
        # Astronomically unlikely, but never emit a duplicate key.
        while candidate in seen:
            discriminator = hashlib.sha1(candidate.encode("utf-8")).hexdigest()[:6]
            candidate = f"{skill.skill_id}~{discriminator}"
        skill.skill_id = candidate
        seen[candidate] = skill

    stats.disambiguated_ids = len(collisions)
    if collisions:
        logger.info(
            "Disambiguated %d colliding skill_id(s) to keep the primary key unique",
            len(collisions),
        )


def deduplicate(skills: list[SkillIndex]) -> tuple[list[SkillIndex], DedupStats]:
    """Remove duplicates, keeping the richest entry for each unique skill.

    Returns (deduped_skills, stats). Stats are surfaced in registry meta.json
    so a regression in dedup quality is visible instead of silent.
    """
    stats = DedupStats(input_count=len(skills))

    after_location, removed_location = _collapse(skills, _location_key, stats)
    stats.removed_by_location = removed_location

    after_content, removed_content = _collapse(after_location, _content_key, stats)
    stats.removed_by_content = removed_content

    _enforce_unique_ids(after_content, stats)

    stats.output_count = len(after_content)

    if stats.removed_count > 0:
        logger.info(
            "Deduplication removed %d duplicates (%d -> %d, %.2f%%) "
            "[by location: %d, by content: %d]",
            stats.removed_count,
            stats.input_count,
            stats.output_count,
            stats.dedup_rate,
            stats.removed_by_location,
            stats.removed_by_content,
        )
        logger.info(
            "  %d skills confirmed by multiple sources (largest group: %d for %s)",
            stats.multi_source_skills,
            stats.largest_group,
            stats.largest_group_key or "n/a",
        )
    else:
        logger.warning(
            "Deduplication removed nothing from %d entries — verify dedup keys",
            stats.input_count,
        )

    return after_content, stats
