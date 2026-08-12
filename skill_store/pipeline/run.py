"""Pipeline orchestrator: runs the full sync → normalize → dedup → score flow."""

from __future__ import annotations

import logging

import skill_store.adapters  # noqa: F401 — triggers adapter self-registration via __init__.py
from skill_store.adapters.base import get_all_adapters, load_sources_config
from skill_store.models import RawSkillEntry, SkillIndex
from skill_store.pipeline.deduplicate import deduplicate
from skill_store.pipeline.normalize import normalize_all
from skill_store.pipeline.score import score_all

logger = logging.getLogger(__name__)


def run_pipeline(source_ids: list[str] | None = None) -> list[SkillIndex]:
    """Execute the full pipeline: crawl → normalize → deduplicate → score.

    Args:
        source_ids: Optional list of source IDs to sync. If None, syncs all enabled sources.

    Returns:
        List of fully processed SkillIndex entries.
    """
    # Load config and create adapters
    sources = load_sources_config()

    if source_ids:
        sources = [s for s in sources if s.id in source_ids]
        logger.info("Filtering to %d specified sources: %s", len(sources), source_ids)

    adapters = get_all_adapters(sources)
    logger.info("Running pipeline with %d adapters", len(adapters))

    # Step 1: Crawl all sources
    all_raw: list[RawSkillEntry] = []
    for adapter in adapters:
        try:
            entries = adapter.sync()
            all_raw.extend(entries)
            logger.info("  [%s] → %d entries", adapter.config.id, len(entries))
        except Exception as e:
            logger.error("  [%s] FAILED: %s", adapter.config.id, e)

    logger.info("Total raw entries: %d", len(all_raw))

    if not all_raw:
        logger.warning("No entries collected from any source")
        return []

    # Step 2: Normalize
    normalized = normalize_all(all_raw)

    # Step 3: Deduplicate
    deduped = deduplicate(normalized)

    # Step 4: Score
    scored = score_all(deduped)

    # Sort by score descending
    scored.sort(key=lambda s: s.score, reverse=True)

    logger.info("Pipeline complete: %d skills in registry", len(scored))
    return scored
