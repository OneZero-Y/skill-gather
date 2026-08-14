"""Core data models for the Skill Store registry.

Follows the agentskills.io specification as the base,
extended with discovery, signals, and platform layers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceType(str, Enum):
    """How this skill was discovered."""

    github_repo = "github_repo"
    awesome_list = "awesome_list"
    web_api = "web_api"
    manual = "manual"


class Category(str, Enum):
    """Top-level skill categories."""

    development = "development"
    creative = "creative"
    document = "document"
    devops = "devops"
    security = "security"
    data = "data"
    content = "content"
    ecommerce = "ecommerce"
    education = "education"
    productivity = "productivity"
    other = "other"


# ---------------------------------------------------------------------------
# Raw entry: what an adapter returns before normalization
# ---------------------------------------------------------------------------


class RawSkillEntry(BaseModel):
    """Raw skill data as returned by an adapter, before normalization."""

    # Identity
    name: str = Field(description="Skill name from source (may not be normalized)")
    description: str = Field(default="", description="Raw description text")

    # Source tracking
    source_id: str = Field(description="Adapter source ID from config.yml")
    source_url: str = Field(description="URL to the skill's origin")
    source_path: str = Field(default="", description="Path within repo (for github_repo)")

    # Optional raw fields
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    # Signals (populated if available at crawl time)
    repo_stars: int | None = None
    last_commit_date: str | None = None
    has_scripts: bool = False
    has_references: bool = False
    file_count: int = 0

    # Extra (adapter-specific data, preserved for debugging)
    extra: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Spec layer: agentskills.io standard fields
# ---------------------------------------------------------------------------


class SkillSpec(BaseModel):
    """Fields from the agentskills.io specification (SKILL.md frontmatter)."""

    name: str = Field(description="1-64 chars, lowercase + hyphens")
    description: str = Field(description="1-1024 chars")
    license: str | None = None
    compatibility: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)
    allowed_tools: str | None = Field(default=None, alias="allowed-tools")


# ---------------------------------------------------------------------------
# Discovery layer: where and how we found it
# ---------------------------------------------------------------------------


class SkillDiscovery(BaseModel):
    """Provenance and source tracking."""

    source_id: str
    source_type: SourceType
    source_url: str
    source_path: str = ""
    install_url: str = ""
    last_synced: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    upstream_commit: str = ""

    # Normalized "owner/repo" when the skill originates from a Git host.
    # Used for content-level dedup and provenance scoring, both of which must
    # work regardless of how each source guessed the in-repo path.
    repo: str = ""

    # Other source_ids that independently indexed this same skill.
    # Populated by the dedup pass; drives the cross-source confirmation signal.
    alternate_sources: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Signals layer: quality indicators
# ---------------------------------------------------------------------------


class SkillSignals(BaseModel):
    """Quantifiable quality indicators (auto-collected)."""

    repo_stars: int = 0
    last_commit_date: str | None = None
    has_scripts: bool = False
    has_references: bool = False
    file_count: int = 0
    open_issues: int | None = None
    install_count: int = 0  # from skills.sh

    # How many independent sources indexed this skill (1 = only one source).
    # Cross-source presence is a trust signal that does not depend on the
    # GitHub API being reachable.
    source_count: int = 1


# ---------------------------------------------------------------------------
# Platform compatibility
# ---------------------------------------------------------------------------


class PlatformCompat(BaseModel):
    """Which platforms/tools can use this skill."""

    claude_code: bool = False
    claude_ai: bool = False
    kiro: bool = False
    codex: bool = False
    universal: bool = False


# ---------------------------------------------------------------------------
# Full skill index entry (the registry record)
# ---------------------------------------------------------------------------


class SkillIndex(BaseModel):
    """Complete skill registry entry — the output stored in registry/skills.json."""

    skill_id: str = Field(description="Globally unique ID, e.g. 'anthropics/mcp-builder'")

    spec: SkillSpec
    discovery: SkillDiscovery
    signals: SkillSignals = Field(default_factory=SkillSignals)
    platform: PlatformCompat = Field(default_factory=PlatformCompat)

    category: Category = Category.other
    tags: list[str] = Field(default_factory=list)
    score: int = Field(default=0, ge=0, le=100)


# ---------------------------------------------------------------------------
# Registry metadata
# ---------------------------------------------------------------------------


class RegistryMeta(BaseModel):
    """Top-level metadata for the registry output."""

    total_skills: int = 0
    sources_count: int = 0
    last_synced: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1"
    categories: dict[str, int] = Field(default_factory=dict)
