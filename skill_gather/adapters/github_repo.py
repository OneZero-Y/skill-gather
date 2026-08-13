"""GitHub Repo adapter: discovers skills from repos with a skills/{name}/SKILL.md structure.

Targets repos like anthropics/skills and openai/skills.
Uses Git Trees API for efficient discovery (one request to get entire file tree).
"""

from __future__ import annotations

import base64
import re
from typing import Any

import yaml

from skill_store.adapters.base import BaseAdapter, SourceConfig, github_client, github_get, register_adapter
from skill_store.models import RawSkillEntry


def _parse_frontmatter(content: str) -> dict[str, Any]:
    """Extract YAML frontmatter from a markdown file."""
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


@register_adapter("github_repo")
class GitHubRepoAdapter(BaseAdapter):
    """Adapter for repos containing skills in a structured directory layout.

    Expected structure:
        {skill_root}/{skill-name}/SKILL.md
        {skill_root}/{skill-name}/scripts/  (optional)
        {skill_root}/{skill-name}/reference/ (optional)
    """

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        self.repo: str = config.get("repo", "")
        self.branch: str = config.get("branch", "main")
        self.skill_root: str = config.get("skill_root", "skills")
        self.skill_marker: str = config.get("skill_marker", "SKILL.md")
        self.license_default: str = config.get("license_default", "")

    def peek_fingerprint(self) -> str | None:
        with github_client() as client:
            sha = self._fetch_branch_sha(client)
            return f"{self.repo}@{self.branch}:{sha}" if sha else None

    def discover(self) -> list[RawSkillEntry]:
        """Use Git Trees API to find all SKILL.md files, then fetch each."""
        with github_client() as client:
            # Step 1: Get the full recursive file tree
            tree = self._fetch_tree(client)
            if not tree:
                return []

            # Step 2: Identify skill directories
            skill_dirs = self._find_skill_dirs(tree)
            self.logger.info("Found %d skill directories in %s", len(skill_dirs), self.repo)

            # Step 3: For each skill, fetch SKILL.md and collect metadata
            commit_sha = self._fetch_branch_sha(client)
            entries = []
            for skill_name, skill_files in skill_dirs.items():
                entry = self._process_skill(client, skill_name, skill_files, commit_sha)
                if entry:
                    entries.append(entry)

            # Step 4: Get repo stars (one extra request)
            stars = self._fetch_repo_stars(client)
            for entry in entries:
                entry.repo_stars = stars

            return entries

    def _fetch_tree(self, client) -> list[dict[str, Any]]:
        """Fetch the complete repo tree recursively."""
        url = f"/repos/{self.repo}/git/trees/{self.branch}?recursive=1"
        resp = github_get(client, url)
        if resp.status_code != 200:
            self.logger.error("Failed to fetch tree for %s: %d", self.repo, resp.status_code)
            return []
        data = resp.json()
        return data.get("tree", [])

    def _fetch_branch_sha(self, client) -> str:
        """Return the current branch HEAD commit SHA (short)."""
        resp = github_get(client, f"/repos/{self.repo}/git/ref/heads/{self.branch}")
        if resp.status_code != 200:
            return ""
        sha = resp.json().get("object", {}).get("sha", "")
        return sha[:12] if sha else ""

    def _find_skill_dirs(self, tree: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        """Group tree entries by skill directory.

        Supports nested layouts such as skills/.curated/{name}/SKILL.md as well as
        the flat skills/{name}/SKILL.md pattern.

        Returns a dict: skill_relative_path -> list of file entries in that skill dir.
        """
        prefix = f"{self.skill_root.rstrip('/')}/"
        marker_suffix = f"/{self.skill_marker}"
        skill_dirs: dict[str, list[dict[str, Any]]] = {}

        for item in tree:
            path: str = item.get("path", "")
            if not path.startswith(prefix) or not path.endswith(marker_suffix):
                continue

            skill_dir = path[: -len(marker_suffix)]
            skill_name = skill_dir[len(prefix):]
            if not skill_name:
                continue

            skill_dirs[skill_name] = [
                f for f in tree
                if f.get("path") == path or f.get("path", "").startswith(f"{skill_dir}/")
            ]

        return skill_dirs

    def _process_skill(
        self, client, skill_name: str, skill_files: list[dict[str, Any]], commit_sha: str = ""
    ) -> RawSkillEntry | None:
        """Fetch SKILL.md content and build a RawSkillEntry."""
        marker_path = f"{self.skill_root}/{skill_name}/{self.skill_marker}"
        content = self._fetch_file_content(client, marker_path)
        if content is None:
            self.logger.warning("Could not fetch %s", marker_path)
            return None

        frontmatter = _parse_frontmatter(content)
        name = frontmatter.get("name", skill_name)
        description = frontmatter.get("description", "")

        # Detect auxiliary files
        file_paths = {f["path"] for f in skill_files}
        has_scripts = any("/scripts/" in p for p in file_paths)
        has_references = any("/reference/" in p or "/references/" in p for p in file_paths)
        has_license = any(p.lower().endswith("license.txt") or p.lower().endswith("license") for p in file_paths)

        license_val = frontmatter.get("license") or (self.license_default if not has_license else None)

        source_url = f"https://github.com/{self.repo}"
        install_url = f"https://github.com/{self.repo}/tree/{self.branch}/{self.skill_root}/{skill_name}"

        return RawSkillEntry(
            name=name,
            description=description,
            source_id=self.config.id,
            source_url=source_url,
            source_path=f"{self.skill_root}/{skill_name}",
            license=license_val,
            compatibility=frontmatter.get("compatibility"),
            metadata=frontmatter.get("metadata") or {},
            has_scripts=has_scripts,
            has_references=has_references,
            file_count=len(skill_files),
            extra={
                "repo": self.repo,
                "branch": self.branch,
                "install_url": install_url,
                "upstream_commit": commit_sha,
                "frontmatter": frontmatter,
            },
        )

    def _fetch_file_content(self, client, path: str) -> str | None:
        """Fetch a single file's content via Contents API."""
        url = f"/repos/{self.repo}/contents/{path}?ref={self.branch}"
        resp = github_get(client, url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        # Content is base64-encoded
        encoded = data.get("content", "")
        if not encoded:
            return None
        try:
            return base64.b64decode(encoded).decode("utf-8")
        except Exception:
            return None

    def _fetch_repo_stars(self, client) -> int:
        """Get the star count for the repo."""
        url = f"/repos/{self.repo}"
        resp = github_get(client, url)
        if resp.status_code != 200:
            return 0
        return resp.json().get("stargazers_count", 0)


# ---------------------------------------------------------------------------
# github_repo_list adapter: multiple individual skill repos
# ---------------------------------------------------------------------------


@register_adapter("github_repo_list")
class GitHubRepoListAdapter(BaseAdapter):
    """Adapter for a list of individual skill repositories.

    Each repo is treated as a single skill. Looks for SKILL.md at repo root
    or in common locations (skills/, .claude/, etc.).
    """

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        self.repos: list[str] = config.get("repos", [])

    def peek_fingerprint(self) -> str | None:
        parts: list[str] = []
        with github_client() as client:
            for repo in sorted(self.repos):
                resp = github_get(client, f"/repos/{repo}")
                if resp.status_code != 200:
                    return None
                pushed = resp.json().get("pushed_at") or ""
                parts.append(f"{repo}:{pushed}")
        return "|".join(parts) if parts else None

    def discover(self) -> list[RawSkillEntry]:
        entries = []
        with github_client() as client:
            for repo in self.repos:
                entry = self._process_repo(client, repo)
                if entry:
                    entries.append(entry)
        return entries

    def _process_repo(self, client, repo: str) -> RawSkillEntry | None:
        """Try to extract skill info from a single repository."""
        self.logger.debug("Processing repo: %s", repo)

        # Try to find SKILL.md in common locations
        skill_content = None
        skill_path = ""
        for candidate in ["SKILL.md", "skills/SKILL.md", ".claude/SKILL.md"]:
            content = self._fetch_file(client, repo, candidate)
            if content:
                skill_content = content
                skill_path = candidate
                break

        # Get repo metadata regardless
        repo_info = self._fetch_repo_info(client, repo)
        if not repo_info:
            self.logger.warning("Could not fetch repo info for %s", repo)
            return None

        name = repo.split("/")[-1]
        description = repo_info.get("description", "") or ""
        stars = repo_info.get("stargazers_count", 0)
        last_push = repo_info.get("pushed_at", "")
        default_branch = repo_info.get("default_branch", "main")

        # If we found a SKILL.md, parse its frontmatter
        frontmatter: dict[str, Any] = {}
        if skill_content:
            frontmatter = _parse_frontmatter(skill_content)
            name = frontmatter.get("name", name)
            description = frontmatter.get("description", description)

        return RawSkillEntry(
            name=name,
            description=description,
            source_id=self.config.id,
            source_url=f"https://github.com/{repo}",
            source_path=skill_path,
            license=frontmatter.get("license") or (repo_info.get("license") or {}).get("spdx_id"),
            compatibility=frontmatter.get("compatibility"),
            metadata=frontmatter.get("metadata") or {},
            repo_stars=stars,
            last_commit_date=last_push[:10] if last_push else None,
            has_scripts=False,
            has_references=False,
            file_count=1 if skill_content else 0,
            extra={
                "repo": repo,
                "has_skill_md": skill_content is not None,
                "install_url": (
                    f"https://github.com/{repo}/tree/{default_branch}/{skill_path}".rstrip("/")
                    if skill_path
                    else f"https://github.com/{repo}/tree/{default_branch}"
                ),
                "frontmatter": frontmatter,
            },
        )

    def _fetch_file(self, client, repo: str, path: str) -> str | None:
        """Attempt to fetch a file from a repo."""
        url = f"/repos/{repo}/contents/{path}"
        resp = github_get(client, url)
        if resp.status_code != 200:
            return None
        data = resp.json()
        encoded = data.get("content", "")
        if not encoded:
            return None
        try:
            return base64.b64decode(encoded).decode("utf-8")
        except Exception:
            return None

    def _fetch_repo_info(self, client, repo: str) -> dict[str, Any] | None:
        """Fetch basic repo info (stars, description, license)."""
        resp = github_get(client, f"/repos/{repo}")
        if resp.status_code != 200:
            return None
        return resp.json()
