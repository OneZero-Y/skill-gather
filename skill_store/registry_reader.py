"""Load and query skills from the local registry."""

from __future__ import annotations

import json
import re
from pathlib import Path

from skill_store.registry_writer import REGISTRY_DIR

_REGISTRY_PATH = REGISTRY_DIR / "skills.json"


def load_skills() -> list[dict]:
    if not _REGISTRY_PATH.exists():
        raise FileNotFoundError(
            f"Registry not found at {_REGISTRY_PATH} — run `skill-store sync` first."
        )
    with open(_REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)["skills"]


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
        skills.sort(key=lambda s: s.get("score", 0), reverse=True)
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
