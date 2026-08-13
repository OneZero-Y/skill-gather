"""Pipeline orchestrator: runs the full sync → normalize → dedup → score flow."""

from __future__ import annotations

import logging

from dataclasses import dataclass, field

import skill_gather.adapters  # noqa: F401 — triggers adapter self-registration via __init__.py
from skill_gather.adapters.base import get_all_adapters, load_sources_config
from skill_gather.models import RawSkillEntry, SkillIndex
from skill_gather.pipeline.deduplicate import deduplicate
from skill_gather.pipeline.normalize import normalize_all
from skill_gather.pipeline.score import score_all
from skill_gather.registry_writer import REGISTRY_DIR, load_existing_skills
from skill_gather.sync_state import load_source_sync_state

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    skills: list[SkillIndex] = field(default_factory=list)
    source_fingerprints: dict[str, str] = field(default_factory=dict)
    skipped_sources: list[str] = field(default_factory=list)
    synced_sources: list[str] = field(default_factory=list)


def run_pipeline(
    source_ids: list[str] | None = None,
    *,
    existing_skills: list[SkillIndex] | None = None,
    force: bool = False,
    incremental: bool = True,
) -> PipelineResult:
    """Execute crawl → normalize → deduplicate → score.

    When incremental=True, skips sources whose upstream fingerprint is unchanged
    and reuses existing registry entries for those sources.
    """
    # Load config and create adapters
    sources = load_sources_config()

    if source_ids:
        sources = [s for s in sources if s.id in source_ids]
        logger.info("Filtering to %d specified sources: %s", len(sources), source_ids)

    adapters = get_all_adapters(sources)
    logger.info("Running pipeline with %d adapters", len(adapters))

    if existing_skills is None:
        existing_skills = load_existing_skills()

    existing_by_source: dict[str, list[SkillIndex]] = {}
    for skill in existing_skills:
        existing_by_source.setdefault(skill.discovery.source_id, []).append(skill)

    stored_state = load_source_sync_state(REGISTRY_DIR) if incremental and not force else {}
    skipped_sources: list[str] = []
    synced_sources: list[str] = []
    source_fingerprints: dict[str, str] = {}

    # Step 1: Crawl sources (or skip unchanged ones)
    all_raw: list[RawSkillEntry] = []
    reused_skills: list[SkillIndex] = []

    for adapter in adapters:
        source_id = adapter.config.id
        stored_fp = stored_state.get(source_id, {}).get("fingerprint")

        if incremental and not force and stored_fp and existing_by_source.get(source_id):
            fingerprint = adapter.peek_fingerprint()
            source_fingerprints[source_id] = fingerprint or stored_fp
            if fingerprint and fingerprint == stored_fp:
                reused = existing_by_source[source_id]
                reused_skills.extend(reused)
                skipped_sources.append(source_id)
                logger.info(
                    "  [%s] unchanged (%s) — reusing %d skills",
                    source_id,
                    fingerprint,
                    len(reused),
                )
                continue

        try:
            entries = adapter.sync()
            # Guard: if sync returned 0 entries but we have existing data,
            # treat it as a soft failure — keep old data rather than silently
            # wiping the source from the registry.
            if not entries and existing_by_source.get(source_id):
                reused = existing_by_source[source_id]
                reused_skills.extend(reused)
                skipped_sources.append(source_id)
                logger.warning(
                    "  [%s] returned 0 entries but registry has %d existing skills "
                    "— keeping existing data (possible API/upstream issue)",
                    source_id,
                    len(reused),
                )
                continue

            all_raw.extend(entries)
            synced_sources.append(source_id)
            fingerprint = adapter.peek_fingerprint()
            if fingerprint:
                source_fingerprints[source_id] = fingerprint
            logger.info("  [%s] → %d entries", source_id, len(entries))
        except Exception as e:
            logger.error("  [%s] FAILED: %s", source_id, e)
            if existing_by_source.get(source_id):
                reused = existing_by_source[source_id]
                reused_skills.extend(reused)
                skipped_sources.append(source_id)
                logger.warning(
                    "  [%s] keeping %d existing skills after sync failure",
                    source_id,
                    len(reused),
                )

    if skipped_sources:
        logger.info(
            "Incremental skip: %d source(s) unchanged — %s",
            len(skipped_sources),
            ", ".join(skipped_sources),
        )

    logger.info("Total raw entries: %d (reused: %d)", len(all_raw), len(reused_skills))

    if not all_raw and not reused_skills:
        logger.warning("No entries collected from any source")
        return PipelineResult()

    # Step 2: Process newly crawled entries (normalize only, no score here)
    new_skills: list[SkillIndex] = []
    if all_raw:
        normalized = normalize_all(all_raw)
        new_skills = list(normalized)

    combined = reused_skills + new_skills
    if not combined:
        return PipelineResult(
            skipped_sources=skipped_sources,
            synced_sources=synced_sources,
            source_fingerprints=source_fingerprints,
        )

    deduped = deduplicate(combined)
    scored = score_all(deduped)
    scored.sort(key=lambda s: s.score, reverse=True)

    for skill in scored:
        sid = skill.discovery.source_id
        source_fingerprints.setdefault(sid, stored_state.get(sid, {}).get("fingerprint", ""))

    logger.info("Pipeline complete: %d skills in registry", len(scored))
    return PipelineResult(
        skills=scored,
        source_fingerprints={k: v for k, v in source_fingerprints.items() if v},
        skipped_sources=skipped_sources,
        synced_sources=synced_sources,
    )
