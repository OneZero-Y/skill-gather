"""Write pipeline output to registry/sources/<id>.json and registry/meta.json.

Storage layout:
  registry/
    sources/
      <source-id>.json          — skills for one source (if < SHARD_SIZE_LIMIT bytes)
      <source-id>-0.json        — shard 0 when a source exceeds SHARD_SIZE_LIMIT
      <source-id>-1.json        — shard 1 …
    meta.json                   — global stats + changelog
    skills_sh_installs.json     — install-count signals (written by skills_sh adapter)

skills.json is no longer written; export_web_data.py reads sources/ directly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skill_gather.models import RegistryMeta, SkillIndex
from skill_gather.sync_state import load_source_sync_state, merge_source_sync_state

logger = logging.getLogger(__name__)

REGISTRY_DIR = Path(__file__).parent.parent / "registry"

# Single source shard file must not exceed this size (bytes).
# GitHub recommends keeping files below 50 MB; we use 40 MB to leave headroom.
SHARD_SIZE_LIMIT = 40 * 1024 * 1024  # 40 MB


# ---------------------------------------------------------------------------
# Source-shard helpers
# ---------------------------------------------------------------------------

def _source_shard_paths(sources_dir: Path, source_id: str) -> list[Path]:
    """Return all existing shard paths for a source, sorted by shard index."""
    single = sources_dir / f"{source_id}.json"
    if single.exists():
        return [single]
    shards = sorted(sources_dir.glob(f"{source_id}-*.json"))
    return list(shards)


def _write_source_shards(
    sources_dir: Path,
    source_id: str,
    records: list[dict],
) -> list[Path]:
    """Write records for one source, splitting into shards if needed.

    Returns the list of paths written.
    """
    sources_dir.mkdir(parents=True, exist_ok=True)

    # Serialise once to measure size
    full_json = json.dumps(
        {"source_id": source_id, "skills": records, "total": len(records),
         "generated_at": datetime.now(timezone.utc).isoformat()},
        ensure_ascii=False,
        indent=2,
        default=_json_default,
    ).encode("utf-8")

    if len(full_json) <= SHARD_SIZE_LIMIT:
        # Fits in a single file
        path = sources_dir / f"{source_id}.json"
        _write_bytes(path, full_json)
        # Remove any stale numbered shards from a previous run
        for stale in sources_dir.glob(f"{source_id}-*.json"):
            stale.unlink(missing_ok=True)
        return [path]

    # Split into numbered shards
    # Estimate records per shard based on average record size
    avg_bytes = len(full_json) / max(len(records), 1)
    records_per_shard = max(1, int(SHARD_SIZE_LIMIT / avg_bytes * 0.9))  # 10% safety margin

    written: list[Path] = []
    for shard_idx, start in enumerate(range(0, len(records), records_per_shard)):
        chunk = records[start: start + records_per_shard]
        path = sources_dir / f"{source_id}-{shard_idx}.json"
        payload = {
            "source_id": source_id,
            "shard": shard_idx,
            "skills": chunk,
            "total": len(records),
            "shard_total": len(chunk),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        _write_json(path, payload)
        written.append(path)

    # Remove single-file version if it exists from a previous run
    single = sources_dir / f"{source_id}.json"
    single.unlink(missing_ok=True)

    logger.info(
        "  %s: %d records split into %d shards",
        source_id, len(records), len(written),
    )
    return written


def load_source_skills(sources_dir: Path, source_id: str) -> list[dict]:
    """Load all skill records for a single source (handles shards transparently)."""
    paths = _source_shard_paths(sources_dir, source_id)
    if not paths:
        return []
    records: list[dict] = []
    for p in paths:
        data = _load_json(p)
        if data:
            records.extend(data.get("skills", []))
    return records


def load_all_source_skills(sources_dir: Path) -> list[dict]:
    """Load and merge all skills from registry/sources/*.json."""
    if not sources_dir.exists():
        return []
    seen_sources: set[str] = set()
    all_records: list[dict] = []
    for path in sorted(sources_dir.glob("*.json")):
        data = _load_json(path)
        if not data:
            continue
        source_id = data.get("source_id", path.stem)
        # De-duplicate shards: track by source_id, each shard contributes its records
        all_records.extend(data.get("skills", []))
        seen_sources.add(source_id)
    return all_records


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_existing_skills(output_dir: Path | None = None) -> list[SkillIndex]:
    """Load current registry entries as SkillIndex models from sources/ shards."""
    out = output_dir or REGISTRY_DIR
    sources_dir = out / "sources"

    # Prefer new sources/ layout; fall back to legacy skills.json for migration
    if sources_dir.exists() and any(sources_dir.glob("*.json")):
        records = load_all_source_skills(sources_dir)
    else:
        legacy = _load_json(out / "skills.json")
        records = legacy.get("skills", []) if legacy else []

    result: list[SkillIndex] = []
    for rec in records:
        try:
            result.append(SkillIndex.model_validate(rec))
        except Exception as e:
            logger.debug("Skipping invalid record: %s", e)
    return result


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


# ---------------------------------------------------------------------------
# JSON helpers
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _write_bytes(path: Path, data: bytes) -> None:
    """Write bytes atomically."""
    import os, tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _write_json(path: Path, data: Any) -> None:
    """Write JSON atomically: write to a temp file then rename."""
    import os, tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


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
    """Compare old registry records against new pipeline results."""
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
    """Write skills to registry/sources/ per-source shards + meta.json.

    Returns the changelog dict from compute_diff.
    """
    out = output_dir or REGISTRY_DIR
    out.mkdir(parents=True, exist_ok=True)
    sources_dir = out / "sources"

    # ------------------------------------------------------------------ #
    # Diff against existing registry (load old records for diff only)
    # ------------------------------------------------------------------ #
    old_skills = load_all_source_skills(sources_dir)
    # Fall back to legacy skills.json during migration
    if not old_skills:
        legacy = _load_json(out / "skills.json")
        old_skills = legacy.get("skills", []) if legacy else []

    changelog = compute_diff(old_skills, skills)

    # ------------------------------------------------------------------ #
    # Write per-source shard files
    # ------------------------------------------------------------------ #
    by_source: dict[str, list[dict]] = {}
    for skill in skills:
        src = skill.discovery.source_id
        by_source.setdefault(src, []).append(skill.model_dump(mode="json"))

    # Remove shard files for sources that no longer have any skills
    existing_source_ids = {
        p.stem.split("-")[0]
        for p in sources_dir.glob("*.json")
        if sources_dir.exists()
    }
    stale_sources = existing_source_ids - set(by_source.keys())
    for stale_id in stale_sources:
        for stale_path in _source_shard_paths(sources_dir, stale_id):
            stale_path.unlink(missing_ok=True)
            logger.info("Removed stale shard: %s", stale_path)

    total_written = 0
    for source_id, records in by_source.items():
        paths = _write_source_shards(sources_dir, source_id, records)
        total_written += len(records)
        logger.info(
            "Wrote %d skills for %s → %s",
            len(records), source_id,
            ", ".join(p.name for p in paths),
        )

    logger.info("Wrote %d skills total → %s", total_written, sources_dir)

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
    prev_sync_state = load_source_sync_state(out)
    source_sync_state = merge_source_sync_state(
        prev_sync_state,
        fingerprints=source_fingerprints or {},
        skill_counts=dict(source_counts),
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
    """Export a frontend-friendly YAML index."""
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
