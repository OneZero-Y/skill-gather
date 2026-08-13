"""Awesome-list adapter: parses a GitHub awesome-list README to extract skill links.

Targets repos like VoltAgent/awesome-agent-skills whose README.md contains
categorized lists of skill repositories in Markdown format.
"""

from __future__ import annotations

import base64
import re

from skill_gather.adapters.base import BaseAdapter, SourceConfig, github_client, github_get, register_adapter
from skill_gather.models import RawSkillEntry

# Pattern: - [name](url) - description
# Also handles: - **[name](url)** - description
_LINK_PATTERN = re.compile(
    r"^\s*[-*]\s+"  # list marker
    r"\*{0,2}"  # optional bold open
    r"\[([^\]]+)\]"  # [name]
    r"\(([^)]+)\)"  # (url)
    r"\*{0,2}"  # optional bold close
    r"\s*[-–—:]\s*"  # separator
    r"(.+)",  # description
    re.MULTILINE,
)

# Pattern for category headers: ## Category or ### Category
_HEADING_PATTERN = re.compile(r"^(#{2,4})\s+(.+)$", re.MULTILINE)


def _is_github_url(url: str) -> bool:
    """Check if a URL points to a GitHub repository."""
    return "github.com/" in url and url.count("/") >= 4


def _extract_repo_from_url(url: str) -> str:
    """Extract owner/repo from a GitHub URL.

    Examples:
        https://github.com/anthropics/skills -> anthropics/skills
        https://github.com/anthropics/skills/tree/main/skills/docx -> anthropics/skills
    """
    url = url.rstrip("/")
    # Remove protocol and domain
    path = re.sub(r"https?://github\.com/", "", url)
    # Take only first two segments (owner/repo)
    parts = path.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return path


@register_adapter("awesome_list")
class AwesomeListAdapter(BaseAdapter):
    """Adapter that parses an awesome-list README for skill links.

    Extracts categorized Markdown links and produces one RawSkillEntry per link.
    Only includes links pointing to GitHub repositories.
    """

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        self.repo: str = config.get("repo", "")
        self.branch: str = config.get("branch", "main")
        self.readme_path: str = config.get("readme_path", "README.md")

    def peek_fingerprint(self) -> str | None:
        with github_client() as client:
            sha = self._fetch_branch_sha(client)
            return f"{self.repo}@{self.branch}:{sha}" if sha else None

    def _fetch_branch_sha(self, client) -> str:
        resp = github_get(client, f"/repos/{self.repo}/git/ref/heads/{self.branch}")
        if resp.status_code != 200:
            return ""
        sha = resp.json().get("object", {}).get("sha", "")
        return sha[:12] if sha else ""

    def discover(self) -> list[RawSkillEntry]:
        """Fetch the README and parse all skill links."""
        with github_client() as client:
            content = self._fetch_readme(client)
            if not content:
                return []

            entries = self._parse_readme(content)

            # Get repo stars for the awesome-list itself (informational)
            self.logger.info(
                "Parsed %d skill links from %s/%s",
                len(entries),
                self.repo,
                self.readme_path,
            )
            return entries

    def _fetch_readme(self, client) -> str | None:
        """Fetch the README file content."""
        url = f"/repos/{self.repo}/contents/{self.readme_path}?ref={self.branch}"
        resp = github_get(client, url)
        if resp.status_code != 200:
            self.logger.error(
                "Failed to fetch README from %s: %d", self.repo, resp.status_code
            )
            return None

        data = resp.json()
        encoded = data.get("content", "")
        if not encoded:
            # Try download_url for large files
            download_url = data.get("download_url")
            if download_url:
                resp2 = client.get(download_url)
                if resp2.status_code == 200:
                    return resp2.text
            return None

        try:
            return base64.b64decode(encoded).decode("utf-8")
        except Exception:
            return None

    def _parse_readme(self, content: str) -> list[RawSkillEntry]:
        """Parse the README markdown to extract skill entries."""
        entries: list[RawSkillEntry] = []
        current_category = ""

        lines = content.split("\n")
        for line in lines:
            # Check for category heading
            heading_match = _HEADING_PATTERN.match(line)
            if heading_match:
                current_category = heading_match.group(2).strip()
                # Clean emoji and special chars from category
                current_category = re.sub(r"[^\w\s/&-]", "", current_category).strip()
                continue

            # Check for skill link
            link_match = _LINK_PATTERN.match(line)
            if link_match:
                name = link_match.group(1).strip()[:64]    # agentskills spec: name max 64
                url = link_match.group(2).strip()
                description = link_match.group(3).strip()[:512]  # guard against runaway descriptions

                # Only process GitHub links
                if not _is_github_url(url):
                    continue

                repo_path = _extract_repo_from_url(url)

                entry = RawSkillEntry(
                    name=name,
                    description=description,
                    source_id=self.config.id,
                    source_url=url,
                    source_path="",
                    extra={
                        "category_raw": current_category,
                        "repo": repo_path,
                        "list_repo": self.repo,
                    },
                )
                entries.append(entry)

        # Deduplicate by source_url (some lists have duplicates)
        seen_urls: set[str] = set()
        unique: list[RawSkillEntry] = []
        for entry in entries:
            if entry.source_url not in seen_urls:
                seen_urls.add(entry.source_url)
                unique.append(entry)

        return unique
