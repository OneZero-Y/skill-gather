"""MCP server for the skill-gather registry.

Lets any MCP-capable host (Claude Code, Kiro, Cursor, Codex, …) query the
aggregated skill index during a session, instead of the user having to leave
the editor and browse a website.

Run it directly:

    uvx skill-gather-mcp          # once published
    uv run skill-gather-mcp       # from a checkout

Design constraints, in priority order:

1. Context frugality. Every byte returned is spent from the host model's
   context budget, so list results are deliberately compact and descriptions
   are truncated. Full detail is only available via `get_skill`.
2. Fail loudly. A missing or unsynced registry raises with an actionable
   message rather than returning an empty list that the model would read as
   "no such skill exists".
3. Read-only. This server never writes to the registry or the user's
   filesystem. Installation stays an explicit user action via the CLI.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server import MCPServer
from pydantic import Field

from skill_gather import registry_reader

mcp = MCPServer("skill-gather")

# Hard ceiling on how many records a single call may return, regardless of what
# the caller asks for — a runaway limit would flood the host's context window.
_MAX_LIMIT = 50
_SUMMARY_DESC_CHARS = 180

_VALID_PLATFORMS = ("claude_code", "claude_ai", "kiro", "codex", "universal")
_VALID_CATEGORIES = (
    "development", "creative", "document", "devops", "security", "data",
    "content", "ecommerce", "education", "productivity", "other",
)


# ---------------------------------------------------------------------------
# Shaping helpers
# ---------------------------------------------------------------------------

def _summary(skill: dict) -> dict[str, Any]:
    """Compact record for list results — optimised for low context cost."""
    spec = skill.get("spec", {})
    discovery = skill.get("discovery", {})
    signals = skill.get("signals", {})

    description = (spec.get("description") or "").strip()
    if len(description) > _SUMMARY_DESC_CHARS:
        description = description[:_SUMMARY_DESC_CHARS].rstrip() + "…"

    return {
        "skill_id": skill.get("skill_id", ""),
        "name": spec.get("name", ""),
        "description": description,
        "category": skill.get("category", "other"),
        "score": skill.get("score", 0),
        "platforms": [k for k in _VALID_PLATFORMS if skill.get("platform", {}).get(k)],
        "source": discovery.get("source_id", ""),
        "repo": discovery.get("repo", ""),
        "stars": signals.get("repo_stars", 0),
        "installs": signals.get("install_count", 0),
    }


def _detail(skill: dict) -> dict[str, Any]:
    """Full record for a single skill, including how to install it."""
    spec = skill.get("spec", {})
    discovery = skill.get("discovery", {})
    signals = skill.get("signals", {})
    skill_id = skill.get("skill_id", "")

    return {
        "skill_id": skill_id,
        "name": spec.get("name", ""),
        "description": spec.get("description", ""),
        "license": spec.get("license") or "",
        "compatibility": spec.get("compatibility") or "",
        "category": skill.get("category", "other"),
        "tags": skill.get("tags", []),
        "score": skill.get("score", 0),
        "platforms": [k for k in _VALID_PLATFORMS if skill.get("platform", {}).get(k)],
        "signals": {
            "stars": signals.get("repo_stars", 0),
            "installs": signals.get("install_count", 0),
            "last_commit": signals.get("last_commit_date"),
            "file_count": signals.get("file_count", 0),
            "has_scripts": signals.get("has_scripts", False),
            "has_references": signals.get("has_references", False),
            # How many independent platforms indexed this skill. >1 is a
            # meaningful trust signal.
            "source_count": signals.get("source_count", 1),
        },
        "provenance": {
            "source": discovery.get("source_id", ""),
            "also_indexed_by": discovery.get("alternate_sources", []),
            "repo": discovery.get("repo", ""),
            "source_url": discovery.get("source_url", ""),
            "install_url": discovery.get("install_url", ""),
            "last_synced": discovery.get("last_synced", ""),
        },
        "install": {
            "cli": f"skill-gather install {skill_id}",
            "browse": discovery.get("install_url", "") or discovery.get("source_url", ""),
        },
    }


def _clamp_limit(limit: int) -> int:
    return max(1, min(_MAX_LIMIT, limit))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def search_skills(
    query: Annotated[
        str,
        Field(description="Keywords to search. Matches skill id, name, description and tags."),
    ],
    category: Annotated[
        str,
        Field(description=f"Optional category filter. One of: {', '.join(_VALID_CATEGORIES)}"),
    ] = "",
    platform: Annotated[
        str,
        Field(description=f"Optional platform filter. One of: {', '.join(_VALID_PLATFORMS)}"),
    ] = "",
    source: Annotated[
        str,
        Field(description="Optional source filter, e.g. 'anthropics-skills'. See list_sources."),
    ] = "",
    min_score: Annotated[
        int,
        Field(description="Only return skills scoring at least this (0-100).", ge=0, le=100),
    ] = 0,
    limit: Annotated[
        int,
        Field(description=f"Max results to return (1-{_MAX_LIMIT}).", ge=1, le=_MAX_LIMIT),
    ] = 10,
) -> dict[str, Any]:
    """Search the aggregated AI agent skill registry.

    Covers skills gathered from official vendor repos, community awesome-lists
    and third-party platforms. Results are ranked by keyword relevance combined
    with a quality score. Use this to find an existing skill before writing one
    from scratch.
    """
    if category and category not in _VALID_CATEGORIES:
        raise ValueError(
            f"Unknown category {category!r}. Valid values: {', '.join(_VALID_CATEGORIES)}"
        )
    if platform and platform not in _VALID_PLATFORMS:
        raise ValueError(
            f"Unknown platform {platform!r}. Valid values: {', '.join(_VALID_PLATFORMS)}"
        )

    results = registry_reader.search_skills(
        query,
        source=source or None,
        category=category or None,
        platform=platform or None,
        min_score=min_score,
        limit=_clamp_limit(limit),
    )

    return {
        "query": query,
        "returned": len(results),
        "filters": {
            k: v for k, v in {
                "category": category,
                "platform": platform,
                "source": source,
                "min_score": min_score or None,
            }.items() if v
        },
        "skills": [_summary(s) for s in results],
        "hint": "Call get_skill with a skill_id for full details and install instructions.",
    }


@mcp.tool()
def get_skill(
    skill_id: Annotated[
        str,
        Field(description="Full skill id, e.g. 'anthropics/skills/xlsx'."),
    ],
) -> dict[str, Any]:
    """Get complete metadata for one skill, including provenance and install steps.

    Accepts a partial id as a convenience: if no exact match exists, the closest
    matches are returned as suggestions instead of an error.
    """
    if not skill_id.strip():
        raise ValueError("skill_id must not be empty.")

    matches = registry_reader.find_skills(skill_id, limit=5)
    if not matches:
        raise ValueError(
            f"No skill found matching {skill_id!r}. "
            "Use search_skills to discover valid skill ids."
        )

    exact = next(
        (s for s in matches if s.get("skill_id", "").lower() == skill_id.strip().lower()),
        None,
    )
    if exact is not None:
        return _detail(exact)

    if len(matches) == 1:
        return _detail(matches[0])

    return {
        "exact_match": False,
        "message": f"No exact match for {skill_id!r}. Closest candidates:",
        "candidates": [_summary(s) for s in matches],
    }


@mcp.tool()
def list_sources() -> dict[str, Any]:
    """List every indexed source with its skill count and sync health.

    Useful for understanding coverage, and for picking a `source` filter for
    search_skills.
    """
    meta = registry_reader.load_meta()

    health = (meta.get("quality") or {}).get("source_health") or {}
    counts = meta.get("source_counts") or {}

    sources = []
    for source_id in sorted(counts, key=lambda s: -counts[s]):
        info = health.get(source_id, {})
        entry = {
            "source_id": source_id,
            "skills": counts[source_id],
            "status": info.get("status", "ok"),
        }
        if info.get("error"):
            entry["error"] = info["error"]
        sources.append(entry)

    return {
        "total_sources": len(sources),
        "total_skills": meta.get("total_skills", 0),
        "last_synced": meta.get("last_synced", ""),
        "sources": sources,
    }


@mcp.tool()
def registry_stats() -> dict[str, Any]:
    """Get registry-wide totals, category breakdown and index quality metrics.

    Quality metrics indicate how much to trust the rankings: a narrow score
    spread or a low `traceable_to_repo` percentage means results are weakly
    differentiated.
    """
    meta = registry_reader.load_meta()
    quality = meta.get("quality") or {}
    return {
        "total_skills": meta.get("total_skills", 0),
        "sources_count": meta.get("sources_count", 0),
        "last_synced": meta.get("last_synced", ""),
        "categories": meta.get("categories", {}),
        "platform_counts": meta.get("platform_counts", {}),
        "score_distribution": meta.get("score_distribution", {}),
        "quality": {
            "score": quality.get("score", {}),
            "coverage_pct": quality.get("coverage_pct", {}),
            "dedup": quality.get("dedup", {}),
        },
    }


def main() -> None:
    """Entry point for `skill-gather-mcp` (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
