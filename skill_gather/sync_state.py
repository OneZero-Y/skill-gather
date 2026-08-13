"""Per-source sync fingerprints for incremental sync."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def load_source_sync_state(registry_dir: Path) -> dict[str, dict[str, Any]]:
    """Load stored upstream fingerprints from registry/meta.json."""
    meta_path = registry_dir / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        import json

        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as exc:
        logger.warning("Could not read source sync state: %s", exc)
        return {}
    state = meta.get("source_sync_state")
    return state if isinstance(state, dict) else {}


def merge_source_sync_state(
    existing: dict[str, dict[str, Any]],
    *,
    fingerprints: dict[str, str],
    skill_counts: dict[str, int],
    synced_sources: set[str],
    skipped_sources: set[str],
) -> dict[str, dict[str, Any]]:
    """Merge fingerprint updates for synced sources; preserve skipped source entries."""
    merged = dict(existing)
    now = datetime.now(timezone.utc).isoformat()

    for source_id in synced_sources:
        fingerprint = fingerprints.get(source_id)
        if not fingerprint:
            continue
        merged[source_id] = {
            "fingerprint": fingerprint,
            "skill_count": skill_counts.get(source_id, 0),
            "synced_at": now,
            "skipped": False,
        }

    for source_id in skipped_sources:
        prev = merged.get(source_id, {})
        merged[source_id] = {
            **prev,
            "fingerprint": prev.get("fingerprint") or fingerprints.get(source_id, ""),
            "skill_count": skill_counts.get(source_id, prev.get("skill_count", 0)),
            "synced_at": prev.get("synced_at", now),
            "skipped": True,
        }

    return merged
