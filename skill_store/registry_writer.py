"""Write pipeline output to registry/skills.json and registry/meta.json.

Also provides diff detection: compare new results against the existing registry
and return a structured changelog (added / removed / modified).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skill_store.models import RegistryMeta, SkillIndex
from skill_store.sync_state import load_source_sync_state, merge_source_sync_state

logger = logging.getLogger(__name__)

REGISTRY_DIR = Path(__file__).parent.parent / "registry"


def merge_skills_for_sources(
    existing: list[SkillIndex],
    incoming: list[SkillIndex],
    source_ids: set[str],
) -> list[SkillIndex]:
    """Replace skills from given sources while keeping all other registry entries."""
    kept = [skill for skill in existing if skill.discovery.source_id not in source_ids]
    merged = kept + incoming
    merged.sort(key=lambda skill: skill.score, reverse=True)
    return merged


def load_existing_skills(output_dir: Path | None = None) -> list[SkillIndex]:
    """Load current registry entries as SkillIndex models."""
    out = output_dir or REGISTRY_DIR
    existing = _load_json(out / "skills.json")
    if not existing:
        return []
    return [SkillIndex.model_validate(record) for record in existing.get("skills", [])]


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)


def _load_json(path: Path) -> Any | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not read %s: %s", path, e)
        return None


# ---------------------------------------------------------------------------
# Diff / change detection
# ---------------------------------------------------------------------------

def compute_diff(
    old_skills: list[dict],
    new_skills: list[SkillIndex],
) -> dict[str, Any]:
    """Compare old registry records against new pipeline results.

    Returns a changelog dict with added / removed / modified lists
    and summary counts.
    """
    old_by_id: dict[str, dict] = {s["skill_id"]: s for s in old_skills}
    new_by_id: dict[str, SkillIndex] = {s.skill_id: s for s in new_skills}

    old_ids = set(old_by_id)
    new_ids = set(new_by_id)

    added = sorted(new_ids - old_ids)
    removed = sorted(old_ids - new_ids)

    modified: list[str] = []
    for skill_id in old_ids & new_ids:
        old = old_by_id[skill_id]
        new = new_by_id[skill_id]
        # A skill is "modified" if description or source URL changed
        if (
            old.get("spec", {}).get("description") != new.spec.description
            or old.get("discovery", {}).get("source_url") != new.discovery.source_url
            or old.get("signals", {}).get("repo_stars") != new.signals.repo_stars
        ):
            modified.append(skill_id)

    changelog = {
        "added": added,
        "removed": removed,
        "modified": modified,
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
            "total_old": len(old_ids),
            "total_new": len(new_ids),
        },
    }

    logger.info(
        "Diff: +%d added, -%d removed, ~%d modified (total: %d → %d)",
        len(added), len(removed), len(modified), len(old_ids), len(new_ids),
    )
    return changelog


# ---------------------------------------------------------------------------
# Main writer
# ---------------------------------------------------------------------------

def write_registry(
    skills: list[SkillIndex],
    output_dir: Path | None = None,
    *,
    source_fingerprints: dict[str, str] | None = None,
    skipped_sources: set[str] | None = None,
    synced_sources: set[str] | None = None,
) -> dict[str, Any]:
    """Write skills to registry/ and return a diff changelog.

    Writes:
      registry/skills.json       — full index
      registry/meta.json         — summary stats + changelog
      registry/by-category/*.json — per-category shards

    Returns:
      The changelog dict from compute_diff (empty if no previous registry).
    """
    out = output_dir or REGISTRY_DIR
    out.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Diff against existing registry
    # ------------------------------------------------------------------ #
    existing = _load_json(out / "skills.json")
    old_skills: list[dict] = existing.get("skills", []) if existing else []
    changelog = compute_diff(old_skills, skills)

    # ------------------------------------------------------------------ #
    # skills.json
    # ------------------------------------------------------------------ #
    skills_payload = {
        "skills": [s.model_dump(mode="json") for s in skills],
        "total": len(skills),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(out / "skills.json", skills_payload)
    logger.info("Wrote %d skills → %s", len(skills), out / "skills.json")

    # ------------------------------------------------------------------ #
    # meta.json
    # ------------------------------------------------------------------ #
    category_counts: dict[str, int] = {}
    source_counts: dict[str, int] = {}
    platform_counts = {
        "claude_code": 0, "claude_ai": 0,
        "kiro": 0, "codex": 0, "universal": 0,
    }

    for skill in skills:
        cat = skill.category.value
        category_counts[cat] = category_counts.get(cat, 0) + 1
        src = skill.discovery.source_id
        source_counts[src] = source_counts.get(src, 0) + 1
        for k in platform_counts:
            if getattr(skill.platform, k, False):
                platform_counts[k] += 1

    source_ids = sorted({s.discovery.source_id for s in skills})
    source_counts_for_state = dict(source_counts)
    prev_sync_state = load_source_sync_state(out)
    source_sync_state = merge_source_sync_state(
        prev_sync_state,
        fingerprints=source_fingerprints or {},
        skill_counts=source_counts_for_state,
        synced_sources=synced_sources or set(),
        skipped_sources=skipped_sources or set(),
    )

    meta = RegistryMeta(
        total_skills=len(skills),
        sources_count=len(source_ids),
        last_synced=datetime.now(timezone.utc),
        categories=category_counts,
    )
    meta_payload = {
        **meta.model_dump(mode="json"),
        "sources": source_ids,
        "source_counts": source_counts,
        "platform_counts": platform_counts,
        "score_distribution": _score_distribution(skills),
        "changelog": changelog["summary"],
        "source_sync_state": source_sync_state,
    }
    _write_json(out / "meta.json", meta_payload)
    logger.info("Wrote registry metadata → %s", out / "meta.json")

    # ------------------------------------------------------------------ #
    # by-category shards
    # ------------------------------------------------------------------ #
    by_cat_dir = out / "by-category"
    by_cat_dir.mkdir(exist_ok=True)

    by_category: dict[str, list[SkillIndex]] = {}
    for skill in skills:
        by_category.setdefault(skill.category.value, []).append(skill)

    for cat, cat_skills in by_category.items():
        _write_json(
            by_cat_dir / f"{cat}.json",
            {
                "category": cat,
                "skills": [s.model_dump(mode="json") for s in cat_skills],
                "total": len(cat_skills),
            },
        )
    logger.info("Wrote %d category shards → %s", len(by_category), by_cat_dir)

    return changelog


# ---------------------------------------------------------------------------
# Export helpers (called from CLI)
# ---------------------------------------------------------------------------

def export_csv(skills: list[dict], output_path: Path) -> None:
    """Export skill records to a CSV file."""
    import csv

    fieldnames = [
        "skill_id", "name", "description", "category", "score",
        "repo_stars", "license", "source_id", "source_url",
        "claude_code", "kiro", "tags",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for s in skills:
            writer.writerow({
                "skill_id":    s.get("skill_id", ""),
                "name":        s.get("spec", {}).get("name", ""),
                "description": s.get("spec", {}).get("description", ""),
                "category":    s.get("category", ""),
                "score":       s.get("score", 0),
                "repo_stars":  s.get("signals", {}).get("repo_stars", 0),
                "license":     s.get("spec", {}).get("license", ""),
                "source_id":   s.get("discovery", {}).get("source_id", ""),
                "source_url":  s.get("discovery", {}).get("source_url", ""),
                "claude_code": s.get("platform", {}).get("claude_code", False),
                "kiro":        s.get("platform", {}).get("kiro", False),
                "tags":        ",".join(s.get("tags", [])),
            })
    logger.info("Exported %d skills to CSV: %s", len(skills), output_path)


def export_yaml(skills: list[dict], output_path: Path) -> None:
    """Export a frontend-friendly YAML index (Phase 2 Astro consumer)."""
    import yaml

    rows = []
    for skill in skills:
        spec = skill.get("spec", {})
        discovery = skill.get("discovery", {})
        signals = skill.get("signals", {})
        rows.append({
            "id": skill.get("skill_id", ""),
            "name": spec.get("name", ""),
            "description": spec.get("description", ""),
            "category": skill.get("category", "other"),
            "score": skill.get("score", 0),
            "tags": skill.get("tags", []),
            "source": discovery.get("source_id", ""),
            "install_url": discovery.get("install_url", ""),
            "stars": signals.get("repo_stars", 0),
            "installs": signals.get("install_count", 0),
            "platforms": [k for k, v in skill.get("platform", {}).items() if v],
        })

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "skills": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
    logger.info("Exported %d skills to YAML: %s", len(skills), output_path)


def _score_distribution(skills: list[SkillIndex]) -> dict[str, int]:
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
