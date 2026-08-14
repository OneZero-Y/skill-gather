"""Normalize raw skill entries into structured SkillIndex records."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from skill_gather.models import (
    Category,
    PlatformCompat,
    RawSkillEntry,
    SkillDiscovery,
    SkillIndex,
    SkillSignals,
    SkillSpec,
    SourceType,
)
from skill_gather.repo_utils import normalize_repo, repo_from_urls

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Platform compatibility: source-level known mappings
# Based on vercel-labs/skills README (76 agents documented)
# and official org documentation.
# ---------------------------------------------------------------------------

# source_id → which platforms are confirmed compatible
_SOURCE_PLATFORM_MAP: dict[str, dict[str, bool]] = {
    "anthropics-skills": {
        "claude_code": True, "claude_ai": True,
        "kiro": False, "codex": False, "universal": False,
    },
    "openai-skills": {
        "claude_code": False, "claude_ai": False,
        "kiro": False, "codex": True, "universal": False,
    },
    "vercel-agent-skills": {
        "claude_code": True, "claude_ai": False,
        "kiro": True, "codex": True, "universal": True,
    },
    "langchain-skills": {
        "claude_code": True, "claude_ai": False,
        "kiro": True, "codex": True, "universal": True,
    },
    "voltagent-awesome": {
        # Items in the awesome list are community skills — mark as universal
        # (they follow the agentskills.io spec)
        "claude_code": True, "claude_ai": False,
        "kiro": True, "codex": True, "universal": True,
    },
    "community-repos": {
        "claude_code": True, "claude_ai": False,
        "kiro": True, "codex": True, "universal": True,
    },
    "skillhub-cn": {
        "claude_code": True, "claude_ai": False,
        "kiro": True, "codex": True, "universal": True,
    },
    "mcpmarket-cn": {
        "claude_code": True, "claude_ai": False,
        "kiro": True, "codex": True, "universal": True,
    },
}

# Text-level hints that override source defaults
_COMPAT_HINTS: list[tuple[str, str, bool]] = [
    # (keyword_in_combined_text, platform_key, value)
    ("claude code",   "claude_code", True),
    ("claude-code",   "claude_code", True),
    ("claude.ai",     "claude_ai",   True),
    ("kiro",          "kiro",        True),
    ("codex",         "codex",       True),
    ("cursor",        "universal",   True),
    ("copilot",       "universal",   True),
    ("opencode",      "universal",   True),
    ("windsurf",      "universal",   True),
    ("gemini cli",    "universal",   True),
]


# ---------------------------------------------------------------------------
# Category inference
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS: dict[Category, list[str]] = {
    Category.development: [
        "dev", "code", "coding", "programming", "sdk", "cli", "build", "test",
        "debug", "framework", "library", "api", "typescript", "python", "rust",
        "go", "frontend", "backend", "fullstack", "web", "mobile", "react",
        "next", "vue", "angular", "langchain", "langgraph",
    ],
    Category.creative: [
        "art", "design", "creative", "music", "video", "image", "animation",
        "illustration", "theme", "brand", "visual", "canvas", "gif", "ppt",
        "presentation", "slides",
    ],
    Category.document: [
        "doc", "document", "pdf", "pptx", "xlsx", "docx", "excel", "word",
        "powerpoint", "spreadsheet", "writing", "markdown", "report",
    ],
    Category.devops: [
        "devops", "deploy", "deployment", "ci", "cd", "infrastructure",
        "terraform", "docker", "kubernetes", "aws", "cloud", "monitoring",
        "ops", "vercel", "cloudflare", "pipeline",
    ],
    Category.security: [
        "security", "secure", "audit", "vulnerability", "pentest", "crypto",
        "auth", "permission", "firewall", "scan", "sast", "sbom",
    ],
    Category.data: [
        "data", "database", "analytics", "ml", "machine learning", "ai research",
        "dataset", "model", "training", "science", "rag", "embedding", "vector",
        "langsmith", "eval",
    ],
    Category.content: [
        "content", "blog", "seo", "marketing", "social", "publish", "article",
        "newsletter", "email", "copywrite", "writing", "editorial",
    ],
    Category.ecommerce: [
        "ecommerce", "e-commerce", "shop", "store", "payment", "checkout",
        "product", "cart", "stripe", "commerce",
    ],
    Category.education: [
        "education", "tutor", "learn", "course", "teaching", "study", "tutorial",
    ],
    Category.productivity: [
        "productivity", "workflow", "automation", "organize", "task", "project",
        "management", "notion", "calendar", "linear", "jira",
    ],
}


def infer_category(entry: RawSkillEntry) -> Category:
    raw_cat = entry.extra.get("category_raw", "")
    text = f"{entry.name} {entry.description} {raw_cat}".lower()

    best_category = Category.other
    best_score = 0

    for category, keywords in _CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


# ---------------------------------------------------------------------------
# Platform compatibility inference
# ---------------------------------------------------------------------------

def infer_platform(entry: RawSkillEntry) -> PlatformCompat:
    # Start from the source-level known defaults
    defaults = _SOURCE_PLATFORM_MAP.get(entry.source_id, {
        "claude_code": True, "claude_ai": False,
        "kiro": True, "codex": False, "universal": False,
    })
    result = dict(defaults)

    # Apply text-level overrides
    combined = (
        f"{entry.compatibility or ''} {entry.description} {entry.name}"
    ).lower()
    for keyword, platform_key, value in _COMPAT_HINTS:
        if keyword in combined:
            result[platform_key] = value

    # If skill has a SKILL.md and isn't explicitly platform-locked, mark universal
    has_skill_md = entry.extra.get("has_skill_md", False) or entry.file_count > 0
    if has_skill_md and not result.get("universal"):
        # Only mark universal if no single platform is exclusively targeted
        compat_flags = [result.get("claude_code"), result.get("kiro"),
                        result.get("codex"), result.get("claude_ai")]
        true_count = sum(1 for f in compat_flags if f)
        exclusively_one = true_count == 1
        if not exclusively_one:
            result["universal"] = True

    return PlatformCompat(**result)


# ---------------------------------------------------------------------------
# Tag extraction
# ---------------------------------------------------------------------------

def extract_tags(entry: RawSkillEntry) -> list[str]:
    tags: set[str] = set()

    # From name: split on hyphens/underscores
    name_parts = re.sub(r"[_\s]", "-", entry.name.lower()).split("-")
    stopwords = {"the", "and", "for", "with", "via", "use", "get", "set"}
    for part in name_parts:
        if len(part) >= 3 and part not in stopwords:
            tags.add(part)

    # From description: extract tech-looking tokens
    desc_tokens = re.findall(r"\b[a-z][a-z0-9]{2,15}\b", entry.description.lower())
    tech_words = {
        "react", "next", "vue", "angular", "typescript", "javascript", "python",
        "rust", "golang", "terraform", "docker", "kubernetes", "aws", "gcp",
        "azure", "stripe", "notion", "linear", "github", "langchain", "langgraph",
        "rag", "llm", "mcp", "api", "cli", "sdk", "pdf", "xlsx", "pptx",
    }
    for token in desc_tokens:
        if token in tech_words:
            tags.add(token)

    # From metadata
    if entry.metadata:
        tags_val = entry.metadata.get("tags", "")
        if isinstance(tags_val, str):
            tags.update(t.strip() for t in tags_val.split(",") if t.strip())

    return sorted(tags)[:12]


# ---------------------------------------------------------------------------
# Skill ID generation
# ---------------------------------------------------------------------------

def generate_skill_id(entry: RawSkillEntry) -> str:
    repo = entry.extra.get("repo", "")
    if repo and "/" in repo:
        if entry.source_path and entry.name != repo.split("/")[-1]:
            return f"{repo}/{entry.name}"
        return repo

    name_slug = re.sub(r"[^a-z0-9-]", "-", entry.name.lower()).strip("-")
    return f"{entry.source_id}/{name_slug}"


# ---------------------------------------------------------------------------
# Repo normalization and description sanity checks
# ---------------------------------------------------------------------------

def _normalize_repo(entry: RawSkillEntry) -> str:
    """Resolve a canonical lowercase 'owner/repo' for this entry, or ''.

    Prefers the adapter-provided repo, falling back to parsing whichever URL
    we have, so the same repo from different sources produces one key.
    """
    resolved = normalize_repo(str(entry.extra.get("repo") or ""))
    if resolved:
        return resolved
    return repo_from_urls(
        str(entry.extra.get("install_url") or ""),
        entry.source_url or "",
    )


def _is_placeholder_description(description: str, raw_name: str, slug: str) -> bool:
    """True when the description carries no information beyond the name."""
    normalized = re.sub(r"[^a-z0-9]+", "", description.lower())
    for name in (raw_name, slug):
        if normalized and normalized == re.sub(r"[^a-z0-9]+", "", name.lower()):
            return True
    return False


# ---------------------------------------------------------------------------
# Main normalization
# ---------------------------------------------------------------------------

def normalize_entry(entry: RawSkillEntry) -> SkillIndex:
    from skill_gather.adapters.skills_sh import get_install_count

    skill_id = generate_skill_id(entry)
    now = datetime.now(timezone.utc)

    source_type = SourceType.github_repo
    if "awesome" in entry.source_id:
        source_type = SourceType.awesome_list
    elif entry.source_id in ("skills-sh-signals",):
        source_type = SourceType.web_api

    install_url = entry.extra.get("install_url", entry.source_url)

    name_normalized = re.sub(r"[^a-z0-9-]", "-", entry.name.lower()).strip("-") or entry.name

    # Several web_api adapters fall back to `description = name` when the
    # upstream record has no description. Treat that as "no description" so it
    # cannot earn description credit during scoring.
    raw_desc = (entry.description or "").strip()
    if raw_desc and _is_placeholder_description(raw_desc, entry.name, name_normalized):
        raw_desc = ""

    spec = SkillSpec(
        name=name_normalized,
        description=raw_desc[:1024],
        license=entry.license,
        compatibility=entry.compatibility,
        metadata=entry.metadata,
    )

    discovery = SkillDiscovery(
        source_id=entry.source_id,
        source_type=source_type,
        source_url=entry.source_url,
        source_path=entry.source_path,
        install_url=install_url,
        last_synced=now,
        upstream_commit=entry.extra.get("upstream_commit", ""),
        repo=_normalize_repo(entry),
    )

    # Merge skills.sh install count into signals
    install_count = get_install_count(name_normalized)
    if not install_count:
        install_count = int(entry.extra.get("install_count") or 0)

    signals = SkillSignals(
        repo_stars=entry.repo_stars or 0,
        last_commit_date=entry.last_commit_date,
        has_scripts=entry.has_scripts,
        has_references=entry.has_references,
        file_count=entry.file_count,
        install_count=install_count,
    )

    platform = infer_platform(entry)
    category = infer_category(entry)
    tags = extract_tags(entry)

    return SkillIndex(
        skill_id=skill_id,
        spec=spec,
        discovery=discovery,
        signals=signals,
        platform=platform,
        category=category,
        tags=tags,
        score=0,
    )


def normalize_all(entries: list[RawSkillEntry]) -> list[SkillIndex]:
    results = []
    for entry in entries:
        try:
            idx = normalize_entry(entry)
            results.append(idx)
        except Exception as e:
            logger.warning("Failed to normalize entry %s: %s", entry.name, e)
    logger.info("Normalized %d/%d entries", len(results), len(entries))
    return results
