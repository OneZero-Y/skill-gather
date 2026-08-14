"""Web API adapter for third-party skill platforms (SkillHub, MCP Market)."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import httpx

from skill_gather.adapters.base import BaseAdapter, SourceConfig, register_adapter
from skill_gather.models import RawSkillEntry

_GITHUB_REPO_RE = re.compile(r"github\.com/([^/\s]+/[^/\s#?]+)")

# Max concurrent page-fetch workers per source
_MAX_WORKERS = 8


def _pick_text(value: Any, *, prefer_zh: bool = True) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if prefer_zh:
            return str(value.get("zh") or value.get("en") or "")
        return str(value.get("en") or value.get("zh") or "")
    return ""


def _extract_github_repo(url: str | None) -> str:
    if not url:
        return ""
    match = _GITHUB_REPO_RE.search(url)
    if not match:
        return ""
    return match.group(1).rstrip("/")


@register_adapter("web_api")
class WebApiAdapter(BaseAdapter):
    """Fetch skills from platform HTTP APIs (SkillHub, MCP Market)."""

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        self.platform: str = config.get("platform", "")
        self.base_url: str = config.get("base_url", "").rstrip("/")
        self.api_path: str = config.get("api_path", "")
        self.page_size: int = int(config.get("page_size", 50))
        self.max_pages: int = int(config.get("max_pages", 10))
        self.sort_by: str = config.get("sort_by", "")
        self.order: str = config.get("order", "")

    def peek_fingerprint(self) -> str | None:
        with self._client() as client:
            if self.platform == "skillhub":
                return self._peek_skillhub(client)
            if self.platform == "mcpmarket":
                return self._peek_mcpmarket(client)
        return None

    def _peek_skillhub(self, client: httpx.Client) -> str | None:
        api_base = self.base_url or "https://api.skillhub.cn"
        path = self.api_path or "/api/skills"
        params: dict[str, str | int] = {"page": 1, "pageSize": self.page_size}
        if self.sort_by:
            params["sortBy"] = self.sort_by
        if self.order:
            params["order"] = self.order
        resp = client.get(f"{api_base}{path}", params=params)
        if resp.status_code != 200:
            return None
        payload = resp.json()
        if payload.get("code") != 0:
            return None
        data = payload.get("data") or {}
        skills = data.get("skills") or []
        first = skills[0] if skills else {}
        return (
            f"skillhub:{data.get('total', 0)}:"
            f"{first.get('updated_at', '')}:{first.get('slug', '')}"
        )

    def _peek_mcpmarket(self, client: httpx.Client) -> str | None:
        site_base = self.base_url or "https://mcpmarket.cn"
        path = self.api_path or "/skills/api/list"
        resp = client.get(f"{site_base}{path}", params={"page": 1, "per_page": self.page_size})
        if resp.status_code != 200:
            return None
        payload = resp.json()
        skills = payload.get("skills") or []
        first = skills[0] if skills else {}
        return (
            f"mcpmarket:{payload.get('total', 0)}:"
            f"{first.get('pushed_at', '')}:{first.get('skill_name', '')}"
        )

    def discover(self) -> list[RawSkillEntry]:
        if self.platform == "skillhub":
            return self._discover_skillhub()
        if self.platform == "mcpmarket":
            return self._discover_mcpmarket()
        self.logger.error(
            "Unknown web_api platform %r for source %s", self.platform, self.config.id
        )
        return []

    def _client(self) -> httpx.Client:
        return httpx.Client(
            headers={"User-Agent": "skill-gather/0.1", "Accept": "application/json"},
            timeout=30.0,
            follow_redirects=True,
        )

    def _discover_skillhub(self) -> list[RawSkillEntry]:
        api_base = self.base_url or "https://api.skillhub.cn"
        path = self.api_path or "/api/skills"

        # ── Step 1: fetch page 1 to learn total count ──────────────────
        def _fetch_page(page: int) -> list[dict]:
            params: dict[str, str | int] = {"page": page, "pageSize": self.page_size}
            if self.sort_by:
                params["sortBy"] = self.sort_by
            if self.order:
                params["order"] = self.order
            with self._client() as client:
                resp = client.get(f"{api_base}{path}", params=params)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"SkillHub API returned HTTP {resp.status_code} on page {page} "
                    f"(body: {resp.text[:200]})"
                )
            payload = resp.json()
            if payload.get("code") != 0:
                raise RuntimeError(
                    f"SkillHub API error code {payload.get('code')}: {payload.get('message')}"
                )
            return payload.get("data", {}).get("skills") or [], int(
                payload.get("data", {}).get("total") or 0
            )

        first_skills, total = _fetch_page(1)
        if not first_skills:
            self.logger.info("SkillHub fetched 0 skills")
            return []

        # Calculate how many pages we actually need
        pages_needed = min(
            self.max_pages,
            -(-total // self.page_size),  # ceil division
        )

        # ── Step 2: fetch remaining pages concurrently ──────────────────
        page_results: dict[int, list[dict]] = {1: first_skills}

        if pages_needed > 1:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                futures = {
                    pool.submit(_fetch_page, p): p
                    for p in range(2, pages_needed + 1)
                }
                for future in as_completed(futures):
                    page = futures[future]
                    try:
                        skills_on_page, _ = future.result()
                        page_results[page] = skills_on_page
                    except Exception as exc:
                        raise RuntimeError(
                            f"SkillHub page {page} failed: {exc}"
                        ) from exc

        # ── Step 3: parse in page order ─────────────────────────────────
        entries: list[RawSkillEntry] = []
        for p in sorted(page_results):
            for item in page_results[p]:
                entry = self._parse_skillhub_item(item)
                if entry:
                    entries.append(entry)

        self.logger.info("SkillHub fetched %d skills (%d pages)", len(entries), pages_needed)
        return entries

    def _parse_skillhub_item(self, item: dict[str, Any]) -> RawSkillEntry | None:
        slug = item.get("slug") or ""
        namespace = item.get("namespace") or {}
        public_slug = namespace.get("publicSlug") or slug
        handle = namespace.get("handle") or item.get("ownerName") or ""

        name = public_slug or slug
        if not name:
            return None

        name = re.sub(r"[^a-z0-9-]", "-", str(name).lower()).strip("-") or str(name)
        desc = _pick_text(item.get("description_zh")) or _pick_text(item.get("description"))
        homepage = item.get("homepage") or ""
        upstream = item.get("upstream_url") or ""
        github_repo = _extract_github_repo(upstream) or _extract_github_repo(homepage)

        if github_repo:
            install_url = upstream or homepage or f"https://github.com/{github_repo}"
            source_url = f"https://github.com/{github_repo}"
        else:
            install_url = homepage or (
                f"https://skillhub.cn/{handle}/{public_slug}" if handle and public_slug else homepage
            )
            source_url = install_url or "https://skillhub.cn"

        return RawSkillEntry(
            name=name,
            description=desc[:1024] if desc else name,
            source_id=self.config.id,
            source_url=source_url,
            source_path=public_slug,
            metadata={
                "platform": "skillhub",
                "source_type": str(item.get("source") or ""),
            },
            repo_stars=int(item.get("stars") or 0),
            file_count=0,
            extra={
                "install_url": install_url,
                "repo": github_repo,
                "category_raw": item.get("category") or "",
                "install_count": int(item.get("downloads") or item.get("installs") or 0),
            },
        )

    def _discover_mcpmarket(self) -> list[RawSkillEntry]:
        site_base = self.base_url or "https://mcpmarket.cn"
        path = self.api_path or "/skills/api/list"

        # ── Step 1: fetch page 1 to learn total_pages ───────────────────
        def _fetch_page(page: int) -> tuple[list[dict], int]:
            params: dict[str, str | int] = {"page": page, "per_page": self.page_size}
            if self.sort_by:
                params["sort"] = self.sort_by
            if self.order:
                params["order"] = self.order
            with self._client() as client:
                resp = client.get(f"{site_base}{path}", params=params)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"MCP Market API returned HTTP {resp.status_code} on page {page} "
                    f"(body: {resp.text[:200]})"
                )
            payload = resp.json()
            return payload.get("skills") or [], int(payload.get("total_pages") or 0)

        first_skills, total_pages = _fetch_page(1)
        if not first_skills:
            self.logger.info("MCP Market fetched 0 skills")
            return []

        pages_needed = min(self.max_pages, total_pages) if total_pages else self.max_pages

        # ── Step 2: fetch remaining pages concurrently ──────────────────
        page_results: dict[int, list[dict]] = {1: first_skills}

        if pages_needed > 1:
            with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
                futures = {
                    pool.submit(_fetch_page, p): p
                    for p in range(2, pages_needed + 1)
                }
                for future in as_completed(futures):
                    page = futures[future]
                    try:
                        skills_on_page, _ = future.result()
                        if skills_on_page:
                            page_results[page] = skills_on_page
                    except Exception as exc:
                        raise RuntimeError(
                            f"MCP Market page {page} failed: {exc}"
                        ) from exc

        # ── Step 3: parse in page order ─────────────────────────────────
        entries: list[RawSkillEntry] = []
        for p in sorted(page_results):
            for item in page_results[p]:
                entry = self._parse_mcpmarket_item(item, site_base)
                if entry:
                    entries.append(entry)

        self.logger.info("MCP Market fetched %d skills (%d pages)", len(entries), pages_needed)
        return entries

    def _parse_mcpmarket_item(
        self, item: dict[str, Any], site_base: str
    ) -> RawSkillEntry | None:
        skill_name = item.get("skill_name") or ""
        if not skill_name:
            return None

        name = re.sub(r"[^a-z0-9-]", "-", skill_name.lower()).strip("-") or skill_name
        desc = _pick_text(item.get("description"))
        repo = item.get("repo_full_name") or ""
        record_id = item.get("_id") or item.get("skill_id") or ""

        if repo:
            source_url = f"https://github.com/{repo}"
            install_url = f"https://github.com/{repo}/tree/main/skills/{skill_name}"
        else:
            source_url = f"{site_base}/skills/{record_id or name}"
            install_url = source_url

        pushed = item.get("pushed_at") or ""
        categories = item.get("categories") or []

        return RawSkillEntry(
            name=name,
            description=desc[:1024] if desc else name,
            source_id=self.config.id,
            source_url=source_url,
            source_path=f"skills/{skill_name}" if repo else str(record_id),
            repo_stars=int(item.get("stars") or item.get("total_stars") or 0),
            last_commit_date=pushed[:10] if pushed else None,
            file_count=0,
            extra={
                "install_url": install_url,
                "repo": repo,
                "category_raw": ", ".join(str(c) for c in categories),
                "install_count": int(item.get("favorite_count") or 0),
            },
        )
