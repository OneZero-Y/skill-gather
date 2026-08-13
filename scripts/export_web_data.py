#!/usr/bin/env python3
"""Export registry/skills.json → web/data/skills.yml for Astro frontend."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

# PyYAML will write strings like '096' without quotes, which js-yaml then
# parses back as the integer 96.  Register a representer that forces quoting
# whenever yaml.safe_load would not give back the same string.
class _SafeDumperWithQuotedStrings(yaml.SafeDumper):
    pass

def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    # If round-tripping through YAML would lose the string, force single-quote style.
    try:
        reloaded = yaml.safe_load(data)
    except Exception:
        reloaded = None
    if not isinstance(reloaded, str) or reloaded != data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="'")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)

_SafeDumperWithQuotedStrings.add_representer(str, _str_representer)


ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "registry" / "skills.json"
META = ROOT / "registry" / "meta.json"
OUTPUT = ROOT / "web" / "data" / "skills.yml"

CATEGORY_LABELS = {
    "development": "开发",
    "creative": "创意",
    "document": "文档",
    "devops": "DevOps",
    "security": "安全",
    "data": "数据",
    "content": "内容",
    "ecommerce": "电商",
    "education": "教育",
    "productivity": "效率",
    "other": "其他",
}


def _row(skill: dict) -> dict:
    spec = skill.get("spec", {})
    discovery = skill.get("discovery", {})
    signals = skill.get("signals", {})
    platform = skill.get("platform", {})
    desc = str((spec.get("description") or ""))
    return {
        "id": str(skill.get("skill_id", "")),
        "name": str(spec.get("name", "")),
        # 列表视图 line-clamp-2 ~80字符，detail 页面由 SSG 各自内联完整数据
        # 160 字符足够列表展示，可节省 ~20% skills.yml 体积
        "description": desc[:160],
        "description_full": desc[:1024],  # detail 页面用
        "category": str(skill.get("category", "other")),
        "score": int(skill.get("score", 0)),
        "tags": [str(t) for t in skill.get("tags", [])][:8],
        "source": str(discovery.get("source_id", "")),
        "install_url": str(discovery.get("install_url", "")),
        "stars": int(signals.get("repo_stars", 0)),
        "installs": int(signals.get("install_count", 0)),
        "platforms": [str(k) for k, v in platform.items() if v],
        "license": str(spec.get("license") or ""),
    }


def _pick_featured(rows: list[dict], n: int = 12) -> list[dict]:
    """Pick featured skills with source diversity (not just top-N by score)."""
    seen_sources: set[str] = set()
    featured: list[dict] = []
    # First pass: one skill per source (highest score)
    for row in rows:
        src = row["source"]
        if src not in seen_sources:
            seen_sources.add(src)
            featured.append(row)
        if len(featured) >= n:
            break
    # Second pass: fill remaining slots from top-scored regardless of source
    if len(featured) < n:
        existing_ids = {r["id"] for r in featured}
        for row in rows:
            if row["id"] not in existing_ids:
                featured.append(row)
                if len(featured) >= n:
                    break
    return featured


def main() -> None:
    if not REGISTRY.exists():
        raise SystemExit(f"Registry not found: {REGISTRY} — run skill-gather sync first.")

    with open(REGISTRY, encoding="utf-8") as f:
        skills_raw = json.load(f)["skills"]

    meta: dict = {}
    if META.exists():
        with open(META, encoding="utf-8") as f:
            meta = json.load(f)

    rows = [_row(s) for s in skills_raw]
    rows.sort(key=lambda r: r["score"], reverse=True)

    categories = meta.get("categories", {})
    category_list = [
        {
            "id": cat_id,
            "name": CATEGORY_LABELS.get(cat_id, cat_id),
            "count": count,
        }
        for cat_id, count in sorted(categories.items(), key=lambda x: -x[1])
    ]

    source_counts = meta.get("source_counts", {})
    source_list = [
        {"id": src_id, "count": count}
        for src_id, count in sorted(source_counts.items(), key=lambda x: -x[1])
    ]

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(rows),
        "site": {
            "title": "Skill Gather",
            "description": "AI Agent Skill 发现引擎 · 兼容性注册表",
        },
        "meta": {
            "last_synced": meta.get("last_synced"),
            "sources_count": meta.get("sources_count", 0),
            "changelog": meta.get("changelog"),
        },
        "categories": category_list,
        "sources": source_list,
        "featured": _pick_featured(rows, n=12),
        "skills": rows,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        yaml.dump(payload, f, Dumper=_SafeDumperWithQuotedStrings, allow_unicode=True, sort_keys=False)

    print(f"✓ Exported {len(rows)} skills → {OUTPUT}")


if __name__ == "__main__":
    main()
