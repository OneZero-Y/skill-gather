"""Quality scoring algorithm for skills.

Computes a 0-100 score based on completeness, popularity, and freshness.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from skill_store.models import SkillIndex

logger = logging.getLogger(__name__)

# Weight configuration
_WEIGHTS = {
    "has_description": 15,
    "has_license": 8,
    "has_scripts": 12,
    "has_references": 8,
    "stars": 15,        # Normalized via log scale
    "installs": 20,     # skills.sh install count (strongest real-world signal)
    "recency": 12,      # How recently updated
    "completeness": 10, # SKILL.md field completeness
}


def _stars_score(stars: int) -> float:
    """Normalize star count to 0-1 using log scale."""
    if stars <= 0:
        return 0.0
    return min(1.0, math.log10(stars + 1) / 3.5)


def _installs_score(installs: int) -> float:
    """Normalize install count from skills.sh to 0-1 using log scale.

    0 = 0, 1K = ~0.43, 100K = ~0.71, 1M = ~0.86
    """
    if installs <= 0:
        return 0.0
    return min(1.0, math.log10(installs + 1) / 7.0)


def _recency_score(last_commit_date: str | None) -> float:
    """Score based on how recently the skill was updated.

    Updated today = 1.0, 30 days ago = 0.7, 180 days = 0.3, 1 year+ = 0.1
    """
    if not last_commit_date:
        return 0.3  # Unknown = neutral

    try:
        last_dt = datetime.fromisoformat(last_commit_date.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0.3

    now = datetime.now(timezone.utc)
    days_ago = (now - last_dt).days

    if days_ago <= 7:
        return 1.0
    elif days_ago <= 30:
        return 0.85
    elif days_ago <= 90:
        return 0.7
    elif days_ago <= 180:
        return 0.5
    elif days_ago <= 365:
        return 0.3
    else:
        return 0.1


def _completeness_score(skill: SkillIndex) -> float:
    """Score based on how many optional fields are filled."""
    filled = 0
    total = 5

    if skill.spec.license:
        filled += 1
    if skill.spec.compatibility:
        filled += 1
    if skill.spec.metadata:
        filled += 1
    if skill.tags:
        filled += 1
    if skill.signals.file_count > 2:
        filled += 1

    return filled / total


def compute_score(skill: SkillIndex) -> int:
    """Compute the quality score (0-100) for a single skill."""
    score = 0.0

    # Binary indicators
    if skill.spec.description:
        score += _WEIGHTS["has_description"]
    if skill.spec.license:
        score += _WEIGHTS["has_license"]
    if skill.signals.has_scripts:
        score += _WEIGHTS["has_scripts"]
    if skill.signals.has_references:
        score += _WEIGHTS["has_references"]

    # Scaled indicators
    score += _stars_score(skill.signals.repo_stars) * _WEIGHTS["stars"]
    score += _installs_score(skill.signals.install_count) * _WEIGHTS["installs"]
    score += _recency_score(skill.signals.last_commit_date) * _WEIGHTS["recency"]
    score += _completeness_score(skill) * _WEIGHTS["completeness"]

    return min(100, max(0, round(score)))


def score_all(skills: list[SkillIndex]) -> list[SkillIndex]:
    """Compute scores for all skills in place."""
    for skill in skills:
        skill.score = compute_score(skill)
    logger.info(
        "Scored %d skills (avg: %.1f, max: %d, min: %d)",
        len(skills),
        sum(s.score for s in skills) / max(len(skills), 1),
        max((s.score for s in skills), default=0),
        min((s.score for s in skills), default=0),
    )
    return skills
