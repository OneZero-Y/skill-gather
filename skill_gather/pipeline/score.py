"""Quality scoring algorithm for skills.

Computes a 0-100 score from completeness, provenance, popularity and freshness.

Design note: the previous version leaned almost entirely on GitHub stars, which
made the whole distribution collapse whenever the GitHub API was unavailable
(observed: max score fell from 91 to 53 during a token outage) and left the
~10k platform-sourced entries indistinguishable from each other.

Two signals fix that, and neither needs the GitHub API at request time:

  provenance   — who publishes it, derived from the repo owner. An
                 `anthropics/*` skill earns official credit whether it was
                 found via direct crawl, MCP Market, or SkillHub.
  cross-source — how many independent platforms indexed the same skill,
                 populated by the dedup pass.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone

from skill_gather.models import SkillIndex

logger = logging.getLogger(__name__)

_WEIGHTS = {
    "has_description": 10,
    "description_quality": 10,
    "has_license": 7,
    "has_scripts": 10,
    "has_references": 7,
    "structure": 7,
    "stars": 10,
    "installs": 15,
    "recency": 9,
    "completeness": 8,
    "provenance": 15,
    "cross_source": 7,
}

# Vendors and foundations whose repos are first-party by definition.
# Matched on the repo owner, so provenance survives being re-indexed by a
# third-party platform.
_OFFICIAL_OWNERS = frozenset({
    # AI labs / model vendors
    "anthropics", "openai", "deepseek-ai", "google", "google-gemini",
    "googleapis", "huggingface", "mistralai", "meta-llama", "microsoft",
    "nvidia", "cohere-ai", "qwenlm", "zhipuai",
    # Cloud / infra
    "aws", "awslabs", "amazon-archives", "azure", "cloudflare", "hashicorp",
    "docker", "kubernetes", "vercel", "vercel-labs", "netlify", "supabase",
    "planetscale", "fly-apps",
    # Dev platforms / tooling
    "github", "gitlab", "atlassian", "jetbrains", "denoland", "oven-sh",
    "astral-sh", "nodejs", "python", "rust-lang", "golang",
    # Frameworks / libraries
    "facebook", "vuejs", "angular", "sveltejs", "remix-run", "withastro",
    "tailwindlabs", "langchain-ai", "run-llama", "pytorch", "tensorflow",
    # Data stores / services
    "mongodb", "redis", "elastic", "qdrant", "pinecone-io", "weaviate",
    "stripe", "twilio", "resend", "sendgrid",
    # Chinese majors
    "bytedance", "alibaba", "tencent", "baidu", "ant-design", "antgroup",
    # Security / QA
    "snyk", "cypress-io", "coderabbitai", "sonarsource",
})

# Source IDs that are curated official collections in their own right.
_OFFICIAL_SOURCE_IDS = frozenset({
    "anthropics-skills",
    "openai-skills",
    "vercel-agent-skills",
    "langchain-skills",
    "aws-agent-toolkit",
    "github-awesome-copilot",
    "microsoft-vscode-skills",
    "supabase-skills",
    "bytedance-deerflow",
})


def _stars_score(stars: int) -> float:
    if stars <= 0:
        return 0.0
    return min(1.0, math.log10(stars + 1) / 3.5)


def _installs_score(installs: int) -> float:
    if installs <= 0:
        return 0.0
    return min(1.0, math.log10(installs + 1) / 7.0)


def _provenance_score(skill: SkillIndex) -> float:
    """Trust in the publisher, independent of live API availability."""
    if skill.discovery.source_id in _OFFICIAL_SOURCE_IDS:
        return 1.0

    repo = skill.discovery.repo
    if repo:
        owner = repo.split("/")[0]
        if owner in _OFFICIAL_OWNERS:
            return 1.0
        # Star count as a proxy for community standing when we have it.
        stars = skill.signals.repo_stars
        if stars >= 10_000:
            return 0.85
        if stars >= 1_000:
            return 0.7
        if stars >= 100:
            return 0.55
        return 0.4

    # No upstream repo. This covers platform-native skills (e.g. SkillHub hosts
    # ~5k entries that are not backed by a public GitHub repo at all), so a flat
    # near-zero would systematically bury a whole ecosystem regardless of how
    # widely its skills are actually used. Fall back to adoption as the trust
    # signal, since it is measured by the hosting platform itself.
    installs = skill.signals.install_count
    if installs >= 10_000:
        return 0.6
    if installs >= 1_000:
        return 0.45
    if installs >= 100:
        return 0.3
    return 0.15


def _cross_source_score(skill: SkillIndex) -> float:
    """Independent confirmation: indexed by how many distinct platforms."""
    count = max(1, skill.signals.source_count)
    if count >= 4:
        return 1.0
    if count == 3:
        return 0.8
    if count == 2:
        return 0.55
    return 0.0


def _recency_score(last_commit_date: str | None) -> float:
    if not last_commit_date:
        return 0.3

    try:
        last_dt = datetime.fromisoformat(last_commit_date.replace("Z", "+00:00"))
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0.3

    days_ago = (datetime.now(timezone.utc) - last_dt).days
    if days_ago <= 7:
        return 1.0
    if days_ago <= 30:
        return 0.85
    if days_ago <= 90:
        return 0.7
    if days_ago <= 180:
        return 0.5
    if days_ago <= 365:
        return 0.3
    return 0.1


def _description_quality_score(description: str) -> float:
    length = len(description.strip())
    if length >= 120:
        return 1.0
    if length >= 40:
        return 0.65
    if length >= 10:
        return 0.35
    return 0.0


def _structure_score(skill: SkillIndex) -> float:
    if skill.signals.file_count >= 5:
        return 1.0
    if skill.signals.file_count >= 2:
        return 0.7
    if skill.signals.file_count >= 1:
        return 0.4
    return 0.0


def _completeness_score(skill: SkillIndex) -> float:
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

    if skill.spec.description:
        score += _WEIGHTS["has_description"]
        score += (
            _description_quality_score(skill.spec.description)
            * _WEIGHTS["description_quality"]
        )
    if skill.spec.license:
        score += _WEIGHTS["has_license"]
    if skill.signals.has_scripts:
        score += _WEIGHTS["has_scripts"]
    if skill.signals.has_references:
        score += _WEIGHTS["has_references"]

    score += _structure_score(skill) * _WEIGHTS["structure"]
    score += _stars_score(skill.signals.repo_stars) * _WEIGHTS["stars"]
    score += _installs_score(skill.signals.install_count) * _WEIGHTS["installs"]
    score += _recency_score(skill.signals.last_commit_date) * _WEIGHTS["recency"]
    score += _completeness_score(skill) * _WEIGHTS["completeness"]
    score += _provenance_score(skill) * _WEIGHTS["provenance"]
    score += _cross_source_score(skill) * _WEIGHTS["cross_source"]

    return min(100, max(0, round(score)))


def score_all(skills: list[SkillIndex]) -> list[SkillIndex]:
    """Compute scores for all skills in place."""
    for skill in skills:
        skill.score = compute_score(skill)

    if not skills:
        return skills

    scores = [s.score for s in skills]
    logger.info(
        "Scored %d skills (avg: %.1f, max: %d, min: %d, p90: %d)",
        len(skills),
        sum(scores) / len(scores),
        max(scores),
        min(scores),
        sorted(scores)[int(len(scores) * 0.9)],
    )
    return skills


def score_distribution(skills: list[SkillIndex]) -> dict[str, int]:
    """Bucketed score histogram, surfaced in registry meta.json."""
    buckets = {"0-20": 0, "21-40": 0, "41-60": 0, "61-80": 0, "81-100": 0}
    for s in skills:
        if s.score <= 20:
            buckets["0-20"] += 1
        elif s.score <= 40:
            buckets["21-40"] += 1
        elif s.score <= 60:
            buckets["41-60"] += 1
        elif s.score <= 80:
            buckets["61-80"] += 1
        else:
            buckets["81-100"] += 1
    return buckets
