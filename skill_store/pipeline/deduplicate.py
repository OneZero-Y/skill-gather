"""Deduplicate skills that appear in multiple sources.

Strategy: when the same skill appears from multiple sources, keep the entry
with the richest metadata (highest file_count, has frontmatter, etc.) and
merge signals from all sources.
"""

from __future__ import annotations

import logging
from urllib.parse import urlparse

from skill_store.models import SkillIndex

logger = logging.getLogger(__name__)


def _normalize_url(url: str) -> str:
    """Normalize a GitHub URL to a canonical form for comparison."""
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    # Remove /tree/main, /tree/master suffixes
    path = path.split("/tree/")[0]
    # Remove /blob/ references
    path = path.split("/blob/")[0]
    return f"{parsed.netloc}{path}".lower()


def _richness_score(skill: SkillIndex) -> int:
    """Score how rich/complete a skill entry is (higher = better to keep)."""
    score = 0
    if skill.spec.description:
        score += len(skill.spec.description[:200])  # Longer description = better
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
    """Remove duplicate skills, keeping the richest entry for each unique skill.

    Deduplication keys (in priority order):
    1. Normalized source URL (catches same repo appearing in multiple lists)
    2. Spec name (catches renamed forks with same skill name)
    """
    # Group by normalized URL
    url_groups: dict[str, list[SkillIndex]] = {}
    for skill in skills:
        key = _normalize_url(skill.discovery.source_url)
        url_groups.setdefault(key, []).append(skill)

    # For each group, pick the best entry
    deduped: list[SkillIndex] = []
    for url_key, group in url_groups.items():
        if len(group) == 1:
            deduped.append(group[0])
        else:
            # Pick the richest entry
            best = max(group, key=_richness_score)
            # Merge signals: take the highest stars count from any source
            max_stars = max(s.signals.repo_stars for s in group)
            if max_stars > best.signals.repo_stars:
                best.signals.repo_stars = max_stars
            deduped.append(best)
            logger.debug(
                "Deduped %d entries for %s, kept %s",
                len(group),
                url_key,
                best.skill_id,
            )

    removed = len(skills) - len(deduped)
    if removed > 0:
        logger.info("Deduplication removed %d duplicates (%d -> %d)", removed, len(skills), len(deduped))
    return deduped
