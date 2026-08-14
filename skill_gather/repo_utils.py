"""Shared helpers for resolving a canonical repo identity from URLs.

Lives in its own module because both the normalize pipeline and the registry
writer need it, and importing the pipeline from the writer would create a
circular import (pipeline.run already imports registry_writer).
"""

from __future__ import annotations

import re

_REPO_URL_RE = re.compile(
    r"(?:github|gitlab|bitbucket)\.com/([^/\s]+/[^/\s#?]+)", re.IGNORECASE
)


def normalize_repo(candidate: str) -> str:
    """Normalize an 'owner/repo' string to a canonical lowercase form.

    Strips a trailing '.git', drops anything past the repo segment, and
    lowercases, so the same repo seen via different sources yields one key.
    Returns '' when the input is not a usable owner/repo pair.
    """
    candidate = (candidate or "").strip()
    if not candidate or "/" not in candidate:
        return ""

    owner, _, repo = candidate.partition("/")
    repo = repo.split("/")[0]
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not owner or not repo:
        return ""
    return f"{owner.lower()}/{repo.lower()}"


def repo_from_urls(*urls: str) -> str:
    """Extract the first resolvable 'owner/repo' from the given URLs."""
    for url in urls:
        if not url:
            continue
        match = _REPO_URL_RE.search(url)
        if match:
            resolved = normalize_repo(match.group(1))
            if resolved:
                return resolved
    return ""
