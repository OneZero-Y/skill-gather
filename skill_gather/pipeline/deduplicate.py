"""Deduplicate skills that appear in multiple sources.

Strategy: when the same skill appears from multiple sources, keep the entry
with the richest metadata (highest file_count, has frontmatter, etc.) and
merge signals from all sources.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from skill_gather.models import SkillIndex

logger = logging.getLogger(__name__)


def _normalize_repo_url(url: str) -> str:
    """Normalize a GitHub URL to owner/repo form."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/").split("/tree/")[0].split("/blob/")[0]
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return f"{parsed.netloc.lower()}/{parts[0]}/{parts[1]}"
    return f"{parsed.netloc.lower()}{path}".lower()


def _normalize_skill_location(url: str) -> str:
    """Normalize a skill URL while preserving its path within the repo."""
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    if len(parts) >= 4 and parts[2] in ("tree", "blob"):
        owner, repo = parts[0], parts[1]
        rest = parts[4:]
        if rest:
            return f"{parsed.netloc.lower()}/{owner}/{repo}/{'/'.join(rest)}"
    return _normalize_repo_url(url)


def _dedup_key(skill: SkillIndex) -> str:
    """Build a stable dedup key for a single skill entry."""
    install_url = skill.discovery.install_url.strip()
    if install_url:
        return _normalize_skill_location(install_url)
    if skill.discovery.source_path:
        return f"{_normalize_repo_url(skill.discovery.source_url)}/{skill.discovery.source_path}".lower()
    return skill.skill_id.lower()


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
    return score


def deduplicate(skills: list[SkillIndex]) -> list[SkillIndex]:
    """Remove duplicate skills, keeping the richest entry for each unique skill."""
    groups: dict[str, list[SkillIndex]] = {}
    for skill in skills:
        groups.setdefault(_dedup_key(skill), []).append(skill)

    deduped: list[SkillIndex] = []
    for key, group in groups.items():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            best = max(group, key=_richness_score)
            max_stars = max(s.signals.repo_stars for s in group)
            if max_stars > best.signals.repo_stars:
                best.signals.repo_stars = max_stars
            deduped.append(best)
            logger.debug(
                "Deduped %d entries for %s, kept %s",
                len(group),
                key,
                best.skill_id,
            )

    removed = len(skills) - len(deduped)
    if removed > 0:
        logger.info("Deduplication removed %d duplicates (%d -> %d)", removed, len(skills), len(deduped))
    return deduped
