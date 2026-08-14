#!/usr/bin/env python3
"""Build the registry snapshot that ships inside the skill bundle.

Marketplaces impose per-file size limits (mcpmarket rejects any file over
500 KB), and the full registry is 18.6 MB across shards up to 8.5 MB each. This
script produces a bundle-sized snapshot in the *same* record schema, so
registry_reader and the CLI need no second code path.

Three independent reductions, measured against the real registry:

  1. Compact encoding. The main registry is written with indent=2 for
     reviewable diffs; 5.8 MB of 18.6 MB was whitespace alone. The bundle is
     never hand-reviewed, so it drops the indentation.
  2. Default elision. Fields at their default (false platform flags, zero
     signals, empty strings) are omitted. Pydantic restores them on load, and
     the CLI reads through .get(), so the records stay equivalent. `platform`
     cost 89 bytes per record to encode five booleans.
  3. Curation. The bundle ships the best skills per category rather than
     everything. A user who wants the full index runs `update`, which is why
     that command exists. Curating per category rather than by a global score
     floor keeps thin categories (education, ecommerce) represented instead of
     letting `development` crowd them out.

Shards are then written under a byte ceiling, since one oversized file fails the
whole import.

    python3 scripts/build_skill_registry.py --output <bundle>/registry
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "registry" / "sources"
SOURCE_META = ROOT / "registry" / "meta.json"

# Keep well under the 500 KB marketplace limit. The writer packs records one at
# a time and closes a shard before crossing this, so the ceiling is a guarantee
# rather than an estimate.
DEFAULT_MAX_SHARD_BYTES = 400 * 1024

# Fields required by registry_reader and the CLI, which index into them
# directly rather than through .get(). These are never elided.
_REQUIRED_DISCOVERY_KEYS = ("source_id",)

_COMPACT_SEPARATORS = (",", ":")


# ---------------------------------------------------------------------------
# Record compaction
# ---------------------------------------------------------------------------

def _is_default(value: object) -> bool:
    """True for values a consumer reconstructs from schema defaults."""
    return value is None or value is False or value == 0 or value == "" or value == []


def compact_record(record: dict, *, description_cap: int) -> dict:
    """Strip defaults and cap the description, preserving the record's shape."""
    out: dict = {}

    for key, value in record.items():
        if key in ("spec", "discovery", "signals", "platform"):
            continue
        if not _is_default(value):
            out[key] = value

    spec = dict(record.get("spec") or {})
    description = (spec.get("description") or "").strip()
    if len(description) > description_cap:
        # Cut on a word boundary when one is close, so the text stays readable.
        cut = description[:description_cap]
        space = cut.rfind(" ")
        spec["description"] = (cut[:space] if space > description_cap * 0.8 else cut).rstrip()
    elif description:
        spec["description"] = description
    else:
        spec.pop("description", None)
    out["spec"] = {k: v for k, v in spec.items() if not _is_default(v)}

    discovery = record.get("discovery") or {}
    out["discovery"] = {
        k: v for k, v in discovery.items()
        if k in _REQUIRED_DISCOVERY_KEYS or not _is_default(v)
    }

    signals = {k: v for k, v in (record.get("signals") or {}).items() if not _is_default(v)}
    if signals:
        out["signals"] = signals

    # Only true platform flags are stored; false ones come back as defaults.
    platform = {k: v for k, v in (record.get("platform") or {}).items() if v}
    if platform:
        out["platform"] = platform

    return out


# ---------------------------------------------------------------------------
# Curation
# ---------------------------------------------------------------------------

def curate(
    records: list[dict],
    *,
    max_per_category: int,
    min_score: int,
) -> tuple[list[dict], dict[str, int]]:
    """Select the highest-scoring records, capped per category.

    Per-category capping rather than a global score floor: `development` holds
    2,769 of the 6,212 records scoring 40+, so a global cut would leave
    `education` with 25 entries and make the bundle useless for those topics.
    """
    by_category: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        if record.get("score", 0) < min_score:
            continue
        by_category[record.get("category") or "other"].append(record)

    selected: list[dict] = []
    kept_per_category: dict[str, int] = {}
    for category, group in by_category.items():
        group.sort(
            key=lambda r: (
                r.get("score", 0),
                (r.get("signals") or {}).get("install_count", 0),
                (r.get("signals") or {}).get("repo_stars", 0),
            ),
            reverse=True,
        )
        chosen = group[:max_per_category]
        kept_per_category[category] = len(chosen)
        selected.extend(chosen)

    selected.sort(key=lambda r: r.get("score", 0), reverse=True)
    return selected, kept_per_category


# ---------------------------------------------------------------------------
# Shard writing
# ---------------------------------------------------------------------------

def write_shards(
    records: list[dict],
    out_dir: Path,
    *,
    max_bytes: int,
) -> list[tuple[str, int]]:
    """Write records into shards, none exceeding max_bytes.

    Records are appended one at a time and the shard is closed before the limit
    is crossed, so the ceiling holds regardless of how the record sizes vary.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Overhead of the wrapper object around the skills array.
    envelope_overhead = 220
    written: list[tuple[str, int]] = []

    shard_index = 0
    current: list[dict] = []
    current_bytes = envelope_overhead

    def flush() -> None:
        nonlocal shard_index, current, current_bytes
        if not current:
            return
        path = out_dir / f"bundle-{shard_index:03d}.json"
        payload = {
            "source_id": f"bundle-{shard_index:03d}",
            "shard": shard_index,
            "skills": current,
            "shard_total": len(current),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        data = json.dumps(payload, ensure_ascii=False, separators=_COMPACT_SEPARATORS)
        path.write_text(data, encoding="utf-8")
        size = path.stat().st_size
        if size > max_bytes:
            raise RuntimeError(
                f"{path.name} is {size} bytes, over the {max_bytes} limit. "
                "Lower --max-shard-bytes or --description-cap."
            )
        written.append((path.name, size))
        shard_index += 1
        current = []
        current_bytes = envelope_overhead

    for record in records:
        encoded = len(
            json.dumps(record, ensure_ascii=False, separators=_COMPACT_SEPARATORS)
            .encode("utf-8")
        ) + 1  # comma
        if current and current_bytes + encoded > max_bytes:
            flush()
        current.append(record)
        current_bytes += encoded

    flush()
    return written


def write_meta(
    out_dir: Path,
    records: list[dict],
    kept_per_category: dict[str, int],
    *,
    source_total: int,
    shards: list[tuple[str, int]],
) -> None:
    """Write meta.json for the bundle, flagged as a curated subset."""
    source_meta = {}
    if SOURCE_META.exists():
        try:
            source_meta = json.loads(SOURCE_META.read_text(encoding="utf-8"))
        except ValueError:
            pass

    sources = sorted({(r.get("discovery") or {}).get("source_id", "") for r in records} - {""})

    platform_counts: dict[str, int] = {}
    for record in records:
        for key, value in (record.get("platform") or {}).items():
            if value:
                platform_counts[key] = platform_counts.get(key, 0) + 1

    scores = sorted(r.get("score", 0) for r in records)
    meta = {
        "total_skills": len(records),
        "sources_count": len(sources),
        "sources": sources,
        "last_synced": source_meta.get("last_synced")
                       or datetime.now(timezone.utc).isoformat(),
        "categories": dict(sorted(kept_per_category.items(), key=lambda kv: -kv[1])),
        "platform_counts": platform_counts,
        # Marks this as a bundle snapshot rather than a full registry, so
        # `doctor` can tell the user that `update` yields more.
        "bundle": {
            "is_subset": True,
            "full_registry_total": source_total,
            "coverage_pct": round(len(records) / source_total * 100, 1) if source_total else 0,
            "selection": "highest score per category",
            "shards": len(shards),
            "score_min": scores[0] if scores else 0,
            "score_max": scores[-1] if scores else 0,
        },
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build(args: argparse.Namespace) -> int:
    if not SOURCE_DIR.exists() or not any(SOURCE_DIR.glob("*.json")):
        print(f"ERROR: no registry at {SOURCE_DIR}. Run `skill-gather sync` first.",
              file=sys.stderr)
        return 1

    records: list[dict] = []
    for shard in sorted(SOURCE_DIR.glob("*.json")):
        try:
            records.extend(json.loads(shard.read_text(encoding="utf-8")).get("skills", []))
        except ValueError as exc:
            print(f"ERROR: {shard.name} is not valid JSON: {exc}", file=sys.stderr)
            return 1

    source_total = len(records)
    print(f"Loaded {source_total} records from the full registry")

    selected, kept_per_category = curate(
        records,
        max_per_category=args.max_per_category,
        min_score=args.min_score,
    )
    if not selected:
        print(
            f"ERROR: curation selected 0 records "
            f"(min_score={args.min_score}). Lower the threshold.",
            file=sys.stderr,
        )
        return 1

    compacted = [
        compact_record(r, description_cap=args.description_cap) for r in selected
    ]

    out_dir = args.output
    sources_dir = out_dir / "sources"
    if sources_dir.exists():
        shutil.rmtree(sources_dir)

    shards = write_shards(compacted, sources_dir, max_bytes=args.max_shard_bytes)
    write_meta(out_dir, compacted, kept_per_category,
               source_total=source_total, shards=shards)

    total_bytes = sum(size for _, size in shards)
    largest = max(shards, key=lambda s: s[1])

    print(f"\nCurated {len(compacted)} of {source_total} records "
          f"({len(compacted) / source_total * 100:.1f}%)")
    print(f"  min_score          {args.min_score}")
    print(f"  max per category   {args.max_per_category}")
    print(f"  description cap    {args.description_cap}")
    print("\nPer category:")
    for category, count in sorted(kept_per_category.items(), key=lambda kv: -kv[1]):
        print(f"  {category:14s} {count}")
    print(f"\nWrote {len(shards)} shard(s) to {sources_dir}")
    print(f"  total    {total_bytes / 1024:8.1f} KB")
    print(f"  largest  {largest[1] / 1024:8.1f} KB  ({largest[0]})")
    print(f"  ceiling  {args.max_shard_bytes / 1024:8.1f} KB")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path,
                        help="Bundle registry directory to write")
    parser.add_argument("--max-per-category", type=int, default=300,
                        help="Cap per category, keeping the highest scores (default: 300)")
    parser.add_argument("--min-score", type=int, default=30,
                        help="Drop records scoring below this (default: 30)")
    parser.add_argument("--description-cap", type=int, default=300,
                        help="Truncate descriptions to this many chars (default: 300)")
    parser.add_argument("--max-shard-bytes", type=int, default=DEFAULT_MAX_SHARD_BYTES,
                        help=f"Per-shard byte ceiling (default: {DEFAULT_MAX_SHARD_BYTES})")
    return build(parser.parse_args())


if __name__ == "__main__":
    sys.exit(main())
