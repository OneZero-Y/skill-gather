#!/usr/bin/env python3
"""Structural checks on an assembled skill bundle, run before publishing.

Guards against shipping a bundle that is internally inconsistent: an entry point
or dependency referring to code that was deliberately excluded, a missing file
the SKILL.md tells the agent to run, or an empty registry snapshot.

Checks parse structure rather than grep raw text. The generated pyproject.toml
legitimately documents in a comment which dependency it removed, so a text
search for that name reports a false positive on a correct bundle.

Standard library only, so it runs on a bare CI image.

    python3 scripts/verify_skill_bundle.py <bundle-dir>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path

# Subpackage intentionally excluded from the bundle, and the dependency that
# exists only to serve it.
EXCLUDED_PACKAGE = "skill_gather/mcp"
EXCLUDED_IMPORT = "skill_gather.mcp"
EXCLUDED_DEPENDENCY = "mcp"

# mcpmarket rejects an import if any individual file is larger than this.
MAX_FILE_BYTES = 500 * 1024

# Files the SKILL.md instructs the agent to run or rely on.
REQUIRED_FILES = (
    "SKILL.md",
    "bin/skill_gather_cli.py",
    "pyproject.toml",
    "requirements.txt",
    "registry/meta.json",
    "skill_gather/main.py",
    "skill_gather/registry_reader.py",
)

_FRONTMATTER_NAME_RE = re.compile(r"^name:\s*(.+)$", re.MULTILINE)


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.notes: list[str] = []

    def check(self, ok: bool, label: str, detail: str = "") -> bool:
        if ok:
            print(f"  OK    {label}")
        else:
            print(f"  FAIL  {label}" + (f" - {detail}" if detail else ""))
            self.failures.append(label)
        return ok

    def note(self, text: str) -> None:
        self.notes.append(text)
        print(f"  info  {text}")


def _requirement_name(requirement: str) -> str:
    return re.split(r"[\s\[<>=!~;]", requirement.strip(), maxsplit=1)[0].lower()


def verify(bundle: Path) -> int:
    print(f"Verifying bundle: {bundle}")

    if not bundle.is_dir():
        print(f"FAIL: not a directory: {bundle}", file=sys.stderr)
        return 1

    r = Report()

    # --- required files -------------------------------------------------
    print("\nRequired files")
    for rel in REQUIRED_FILES:
        r.check((bundle / rel).is_file(), f"{rel} present")

    # --- excluded package is really gone --------------------------------
    print("\nExcluded package")
    r.check(
        not (bundle / EXCLUDED_PACKAGE).exists(),
        f"{EXCLUDED_PACKAGE}/ excluded",
    )

    offenders: list[str] = []
    for py in (bundle / "skill_gather").rglob("*.py"):
        try:
            text = py.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if EXCLUDED_IMPORT in stripped and (
                "import" in stripped or "from" in stripped
            ):
                offenders.append(f"{py.relative_to(bundle)}:{lineno}")
    r.check(
        not offenders,
        f"no shipped module imports {EXCLUDED_IMPORT}",
        "; ".join(offenders[:5]),
    )

    # --- pyproject consistency ------------------------------------------
    print("\npyproject.toml")
    pyproject_path = bundle / "pyproject.toml"
    if pyproject_path.is_file():
        data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project = data.get("project", {})

        dep_names = {_requirement_name(d) for d in project.get("dependencies", [])}
        r.check(
            EXCLUDED_DEPENDENCY not in dep_names,
            f"'{EXCLUDED_DEPENDENCY}' not in dependencies",
            f"found in {sorted(dep_names)}",
        )
        r.note(f"dependencies: {len(dep_names)} ({', '.join(sorted(dep_names))})")

        scripts = project.get("scripts", {}) or {}
        dangling = {
            name: target
            for name, target in scripts.items()
            if EXCLUDED_IMPORT in target
        }
        r.check(
            not dangling,
            "no console script targets excluded code",
            str(dangling),
        )
        r.note(f"console scripts: {', '.join(scripts) or 'none'}")
    else:
        r.check(False, "pyproject.toml parseable", "file missing")

    # --- requirements.txt -----------------------------------------------
    print("\nrequirements.txt")
    req_path = bundle / "requirements.txt"
    if req_path.is_file():
        pinned = []
        for line in req_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith(("#", "-")):
                continue
            pinned.append(_requirement_name(line))
        r.check(
            EXCLUDED_DEPENDENCY not in pinned,
            f"'{EXCLUDED_DEPENDENCY}' not pinned in requirements.txt",
        )
        r.check(len(pinned) > 0, "requirements.txt is not empty")
        r.note(f"pinned packages: {len(pinned)}")
    else:
        r.check(False, "requirements.txt present")

    # --- SKILL.md frontmatter -------------------------------------------
    # mcpmarket requires name (1-64 chars, lowercase/digits/hyphen) and
    # description (1-1024 chars).
    print("\nSKILL.md frontmatter")
    skill_md = bundle / "SKILL.md"
    if skill_md.is_file():
        text = skill_md.read_text(encoding="utf-8")
        r.check(text.startswith("---"), "starts with YAML frontmatter")

        _, _, rest = text.partition("---")
        frontmatter, sep, body = rest.partition("\n---")
        r.check(bool(sep), "frontmatter block is closed")

        match = _FRONTMATTER_NAME_RE.search(frontmatter)
        name = match.group(1).strip().strip("'\"") if match else ""
        r.check(bool(name), "name field present")
        r.check(
            bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)),
            "name is a valid slug (lowercase, digits, hyphens)",
            repr(name),
        )
        r.check(1 <= len(name) <= 64, "name length within 1-64", str(len(name)))

        r.check("description:" in frontmatter, "description field present")
        desc_len = len(
            re.sub(r"\s+", " ", frontmatter.split("description:", 1)[-1]).strip()
        ) if "description:" in frontmatter else 0
        r.check(0 < desc_len <= 1024, "description length within 1-1024", str(desc_len))

        r.check(bool(body.strip()), "body is not empty")

        # Every command the SKILL.md tells the agent to run must exist.
        for referenced in set(re.findall(r"bin/[\w./-]+\.py", body)):
            r.check((bundle / referenced).is_file(), f"referenced file exists: {referenced}")

        # Commands the agent is told to run must be portable. Only fenced code
        # blocks are checked: prose may legitimately mention a construct in
        # order to explain it, and flagging that would be a false positive.
        code_blocks = re.findall(r"```[^\n]*\n(.*?)```", body, re.DOTALL)
        commands = "\n".join(code_blocks)
        for bad in ('dirname "$0"', "dirname $0", "if [ -n", "if [ -z", "&&", "||"):
            r.check(
                bad not in commands,
                f"no non-portable shell construct in commands: {bad}",
            )
        r.note(f"command blocks checked: {len(code_blocks)}")
    else:
        r.check(False, "SKILL.md present")

    # --- registry snapshot ----------------------------------------------
    print("\nRegistry snapshot")
    meta_path = bundle / "registry" / "meta.json"
    shards = sorted((bundle / "registry" / "sources").glob("*.json"))
    r.check(len(shards) > 0, "registry has at least one source shard", f"{len(shards)} found")

    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            total = meta.get("total_skills", 0)
            r.check(total > 0, "meta.json reports a non-zero skill total", str(total))
            r.note(f"snapshot: {total} skills, {meta.get('sources_count', '?')} sources, "
                   f"synced {str(meta.get('last_synced', '?'))[:19]}")
            bundle_info = meta.get("bundle") or {}
            if bundle_info:
                r.note(f"subset: {bundle_info.get('coverage_pct')}% of "
                       f"{bundle_info.get('full_registry_total')} full-registry records, "
                       f"scores {bundle_info.get('score_min')}-{bundle_info.get('score_max')}")
        except ValueError as exc:
            r.check(False, "meta.json is valid JSON", str(exc))

    # --- marketplace file size limit ------------------------------------
    # mcpmarket rejects the entire import if any single file exceeds 500 KB.
    # This is checked here because that rejection happens after publishing,
    # when the bundle is already committed to the public repo.
    print("\nMarketplace size limits")
    oversized = [
        (p.relative_to(bundle), p.stat().st_size)
        for p in bundle.rglob("*")
        if p.is_file() and p.stat().st_size > MAX_FILE_BYTES
    ]
    r.check(
        not oversized,
        f"no file exceeds {MAX_FILE_BYTES // 1024} KB",
        "; ".join(f"{name} is {size // 1024} KB" for name, size in oversized[:5]),
    )
    if shards:
        largest = max(shards, key=lambda p: p.stat().st_size)
        r.note(f"largest shard: {largest.name} at {largest.stat().st_size / 1024:.1f} KB")
        bundle_bytes = sum(f.stat().st_size for f in bundle.rglob("*") if f.is_file())
        r.note(f"bundle total: {bundle_bytes / 1024 / 1024:.1f} MB")

    # --- build artifacts must not be committed --------------------------
    print("\nCleanliness")
    r.check(not (bundle / ".venv").exists(), "no .venv in bundle")
    r.check(
        not list(bundle.rglob("__pycache__")),
        "no __pycache__ directories",
    )
    r.check(not list(bundle.rglob("*.pyc")), "no .pyc files")
    r.check(not (bundle / ".env").exists(), "no .env file (would leak credentials)")

    # --- result ---------------------------------------------------------
    file_count = sum(1 for p in bundle.rglob("*") if p.is_file())
    size_mb = sum(p.stat().st_size for p in bundle.rglob("*") if p.is_file()) / 1024 / 1024
    print(f"\nBundle: {file_count} files, {size_mb:.1f} MB")

    if r.failures:
        print(f"\nFAILED: {len(r.failures)} check(s) did not pass:", file=sys.stderr)
        for failure in r.failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nAll checks passed.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path, help="Path to the assembled bundle")
    args = parser.parse_args()
    return verify(args.bundle)


if __name__ == "__main__":
    sys.exit(main())
