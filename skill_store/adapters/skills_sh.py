"""skills.sh adapter — fetches install-count signals for known skill repos.

skills.sh (https://skills.sh) tracks how many times each skill has been
installed via the `npx skills` CLI. This adapter scrapes the public page for
each configured repo and extracts per-skill install counts, which are then
merged into the signals layer during enrichment.

This adapter is a SIGNAL ENRICHER, not a discoverer: it produces no new
RawSkillEntry records by itself. Instead it writes a side-channel JSON file
`registry/skills_sh_installs.json` that the pipeline uses to populate
`signals.install_count` during normalisation.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import httpx

from skill_store.adapters.base import BaseAdapter, SourceConfig, register_adapter
from skill_store.models import RawSkillEntry

logger = logging.getLogger(__name__)

_SKILLS_SH_BASE = "https://skills.sh"
_OUTPUT_PATH = Path(__file__).parent.parent.parent / "registry" / "skills_sh_installs.json"

# Pattern to extract skill rows from skills.sh HTML:
# Each row looks like:   skill-name  768.1K
_ROW_PATTERN = re.compile(
    r"([a-z][a-z0-9-]{1,63})"   # skill name slug
    r"\s+"
    r"([\d.]+[KMB]?)"           # install count e.g. 768.1K, 2.3M
)


def _parse_count(raw: str) -> int:
    """Convert '768.1K', '2.3M', '45' → integer."""
    raw = raw.strip()
    try:
        if raw.endswith("K"):
            return int(float(raw[:-1]) * 1_000)
        if raw.endswith("M"):
            return int(float(raw[:-1]) * 1_000_000)
        if raw.endswith("B"):
            return int(float(raw[:-1]) * 1_000_000_000)
        return int(raw)
    except ValueError:
        return 0


@register_adapter("skills_sh")
class SkillsShAdapter(BaseAdapter):
    """Fetch install-count data from skills.sh for enrichment.

    Does not return any RawSkillEntry — returns [] from discover().
    Side-effect: writes registry/skills_sh_installs.json.
    """

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        self.repos: list[str] = config.get("repos", [])

    def discover(self) -> list[RawSkillEntry]:
        """Fetch install data and persist to registry/skills_sh_installs.json."""
        all_installs: dict[str, dict[str, int]] = {}

        with httpx.Client(
            headers={"User-Agent": "skill-store/0.1"},
            timeout=20.0,
            follow_redirects=True,
        ) as client:
            for repo in self.repos:
                data = self._fetch_repo_installs(client, repo)
                if data:
                    all_installs[repo] = data
                    self.logger.info(
                        "skills.sh [%s]: %d skills with install data", repo, len(data)
                    )

        if all_installs:
            _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(_OUTPUT_PATH, "w", encoding="utf-8") as f:
                json.dump(all_installs, f, ensure_ascii=False, indent=2)
            self.logger.info(
                "Wrote skills.sh install data for %d repos → %s",
                len(all_installs),
                _OUTPUT_PATH,
            )

        # This adapter never adds entries to the main pipeline
        return []

    def _fetch_repo_installs(self, client: httpx.Client, repo: str) -> dict[str, int]:
        """Scrape the skills.sh page for a repo and return {skill_name: install_count}."""
        url = f"{_SKILLS_SH_BASE}/{repo}"
        try:
            resp = client.get(url)
            if resp.status_code != 200:
                self.logger.warning("skills.sh returned %d for %s", resp.status_code, repo)
                return {}

            text = resp.text
            # Extract all (skill_name, count) pairs from the page text
            matches = _ROW_PATTERN.findall(text)
            result: dict[str, int] = {}
            for skill_name, count_raw in matches:
                count = _parse_count(count_raw)
                if count > 0:
                    result[skill_name] = count

            return result

        except Exception as e:
            self.logger.warning("Failed to fetch skills.sh data for %s: %s", repo, e)
            return {}


# ──────────────────────────────────────────────────────────────────────────────
# Public helper used by normalize.py to look up install counts
# ──────────────────────────────────────────────────────────────────────────────

_installs_cache: dict[str, dict[str, int]] | None = None


def get_install_count(skill_name: str) -> int:
    """Look up the install count for a skill from the cached skills.sh data.

    Returns 0 if data is unavailable or the skill is not found.
    """
    global _installs_cache
    if _installs_cache is None:
        if _OUTPUT_PATH.exists():
            try:
                with open(_OUTPUT_PATH, encoding="utf-8") as f:
                    _installs_cache = json.load(f)
            except Exception:
                _installs_cache = {}
        else:
            _installs_cache = {}

    # Search across all repos
    for _repo, skills in _installs_cache.items():
        if skill_name in skills:
            return skills[skill_name]
    return 0
