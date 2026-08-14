"""Load and query skills from the local registry (registry/sources/*.json)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from skill_gather.registry_writer import REGISTRY_DIR, load_all_source_skills

# ---------------------------------------------------------------------------
# Cached loader
#
# The MCP server calls into this on every tool invocation, and the merged
# registry can be tens of MB. Cache the parsed result and invalidate on the
# newest shard mtime so a background sync is picked up without a restart.
# ---------------------------------------------------------------------------

_cache: list[dict] | None = None
_cache_signature: tuple[int, float] | None = None


def _sources_dir() -> Path:
    return REGISTRY_DIR / "sources"


def _signature(sources_dir: Path) -> tuple[int, float]:
    """Cheap change-detection signature: (shard count, newest mtime)."""
    shards = list(sources_dir.glob("*.json"))
    if not shards:
        return (0, 0.0)
    return (len(shards), max(p.stat().st_mtime for p in shards))


def load_meta() -> dict:
    """Load registry/meta.json.

    Raises FileNotFoundError if the registry has never been synced, rather than
    returning an empty dict — a caller reading `{}` as "no skills exist" would
    be a silent, misleading failure.
    """
    meta_path = REGISTRY_DIR / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(
            f"Registry metadata not found at {meta_path} — run `skill-gather sync` first."
        )
    with open(meta_path, encoding="utf-8") as f:
        return json.load(f)


def load_skills(*, refresh: bool = False) -> list[dict]:
    """Load all skill records, merging every per-source shard.

    Raises FileNotFoundError if the registry has never been synced.
    """
    global _cache, _cache_signature

    sources_dir = _sources_dir()
    if not sources_dir.exists() or not any(sources_dir.glob("*.json")):
        raise FileNotFoundError(
            f"Registry not found at {sources_dir} — run `skill-gather sync` first."
        )

    signature = _signature(sources_dir)
    if refresh or _cache is None or signature != _cache_signature:
        _cache = load_all_source_skills(sources_dir)
        _cache_signature = signature

    return _cache


def find_skills(query: str, *, limit: int = 20) -> list[dict]:
    """Find skills by exact or partial skill_id / name match."""
    query = query.strip().lower()
    if not query:
        return []

    skills = load_skills()
    exact = [s for s in skills if s["skill_id"].lower() == query]
    if exact:
        return exact

    partial: list[tuple[int, dict]] = []
    for skill in skills:
        skill_id = skill["skill_id"].lower()
        name = skill.get("spec", {}).get("name", "").lower()
        if query in skill_id or query == name or skill_id.endswith(f"/{query}"):
            partial.append((skill.get("score", 0), skill))

    partial.sort(key=lambda item: (-item[0], len(item[1]["skill_id"])))
    return [skill for _, skill in partial[:limit]]


def _tokenize(query: str) -> list[str]:
    return [part for part in re.split(r"\s+", query.strip().lower()) if part]


def search_skills(
    query: str,
    *,
    source: str | None = None,
    category: str | None = None,
    platform: str | None = None,
    min_score: int = 0,
    limit: int = 50,
) -> list[dict]:
    """Search skills by keywords across id, name, description, and tags."""
    tokens = _tokenize(query)
    skills = load_skills()

    if source:
        skills = [s for s in skills if s["discovery"]["source_id"] == source]
    if category:
        skills = [s for s in skills if s.get("category") == category]
    if platform:
        skills = [s for s in skills if s.get("platform", {}).get(platform)]
    if min_score:
        skills = [s for s in skills if s.get("score", 0) >= min_score]

    if not tokens:
        skills = sorted(skills, key=lambda s: s.get("score", 0), reverse=True)
        return skills[:limit]

    scored: list[tuple[int, dict]] = []
    for skill in skills:
        spec = skill.get("spec", {})
        haystack = " ".join(
            [
                skill.get("skill_id", ""),
                spec.get("name", ""),
                spec.get("description", ""),
                " ".join(skill.get("tags", [])),
                skill.get("category", ""),
            ]
        ).lower()
        if not all(token in haystack for token in tokens):
            continue

        relevance = sum(
            3 if token == spec.get("name", "").lower() else
            2 if token in skill.get("skill_id", "").lower() else 1
            for token in tokens
        )
        scored.append((relevance * 100 + skill.get("score", 0), skill))

    scored.sort(key=lambda item: item[0], reverse=True)
    return [skill for _, skill in scored[:limit]]
