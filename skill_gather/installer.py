"""Install skills from registry install_url into a local agent skills directory."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_GITHUB_TREE_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/tree/(?P<branch>[^/]+)(?P<path>/.*)?$"
)
_GITHUB_REPO_RE = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/?#]+)/?$"
)
_SKILLHUB_API_RE = re.compile(
    r"^https?://api\.skillhub\.cn/(?P<handle>[^/]+)/(?P<slug>[^/]+)/?$"
)

DEFAULT_TARGETS = {
    "cursor": Path.home() / ".cursor" / "skills",
    "claude": Path.home() / ".claude" / "skills",
    "kiro": Path.home() / ".kiro" / "skills",
    "openclaw": Path.home() / ".openclaw" / "skills",
    "hermes": Path.home() / ".hermes" / "skills",
    "project-cursor": Path.cwd() / ".cursor" / "skills",
    "project-claude": Path.cwd() / ".claude" / "skills",
    "project-kiro": Path.cwd() / ".kiro" / "skills",
}


@dataclass(frozen=True)
class GitHubInstallSpec:
    owner: str
    repo: str
    branch: str
    skill_path: str  # directory path inside the repo, may be ""


def parse_github_install_url(url: str) -> GitHubInstallSpec | None:
    url = url.strip().rstrip("/")
    match = _GITHUB_TREE_RE.match(url)
    if match:
        path = (match.group("path") or "").lstrip("/")
        return GitHubInstallSpec(
            owner=match.group("owner"),
            repo=match.group("repo"),
            branch=match.group("branch"),
            skill_path=path,
        )

    match = _GITHUB_REPO_RE.match(url)
    if match:
        return GitHubInstallSpec(
            owner=match.group("owner"),
            repo=match.group("repo"),
            branch="main",
            skill_path="",
        )

    parsed = urlparse(url)
    if parsed.netloc.lower() == "github.com":
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 2:
            return GitHubInstallSpec(
                owner=parts[0],
                repo=parts[1],
                branch="main",
                skill_path="",
            )
    return None


def _validate_skill_path(skill_path: str) -> None:
    """Raise ValueError if skill_path contains path-traversal sequences."""
    if not skill_path:
        return
    # Reject absolute paths and any component that is ".."
    p = Path(skill_path)
    if p.is_absolute():
        raise ValueError(f"skill_path must be relative, got: {skill_path!r}")
    if ".." in p.parts:
        raise ValueError(f"skill_path contains path-traversal sequence: {skill_path!r}")


def _sanitize_skill_name(name: str) -> str:
    """Return a safe filesystem name derived from a skill name."""
    cleaned = re.sub(r"[^a-z0-9_.\-]", "-", name.lower()).strip("-.")
    if not cleaned:
        raise ValueError(f"Cannot derive safe name from: {name!r}")
    return cleaned
    """Extract SkillHub slug from a registry skill record."""
    discovery = skill.get("discovery") or {}
    source_id = discovery.get("source_id", "")
    install_url = (discovery.get("install_url") or "").strip()

    match = _SKILLHUB_API_RE.match(install_url)
    if match:
        return match.group("slug")

    if source_id == "skillhub-cn":
        skill_id = skill.get("skill_id", "")
        if skill_id.startswith("skillhub-cn/"):
            return skill_id.split("/", 1)[1]
        source_path = discovery.get("source_path") or ""
        if source_path:
            return source_path
    return None


def resolve_target(
    target: str | None,
    *,
    preset: str | None,
) -> Path:
    if target:
        return Path(target).expanduser().resolve()
    if preset and preset in DEFAULT_TARGETS:
        return DEFAULT_TARGETS[preset].expanduser().resolve()
    return DEFAULT_TARGETS["cursor"].expanduser().resolve()


def install_skill(
    skill: dict,
    target_dir: Path,
    *,
    force: bool = False,
) -> Path:
    """Install a registry skill into target_dir. Returns destination path."""
    install_url = skill.get("discovery", {}).get("install_url", "")
    raw_name = skill.get("spec", {}).get("name") or skill["skill_id"].split("/")[-1]
    skill_name = _sanitize_skill_name(raw_name)
    dest = target_dir / skill_name

    if dest.exists():
        if not force:
            raise FileExistsError(
                f"Skill already exists at {dest} — use --force to overwrite."
            )
        shutil.rmtree(dest)

    target_dir.mkdir(parents=True, exist_ok=True)

    spec = parse_github_install_url(install_url)
    if spec is not None:
        _install_from_github(spec, dest)
        return dest

    skillhub_slug = parse_skillhub_slug(skill)
    if skillhub_slug is not None:
        return _install_from_skillhub(skillhub_slug, target_dir, dest, force=force)

    raise ValueError(
        f"Automatic install is not supported for {install_url!r}. "
        "Open the URL and install manually, or use the skillhub CLI for SkillHub skills."
    )


def _install_from_github(spec: GitHubInstallSpec, dest: Path) -> None:
    # Validate skill_path before any filesystem or git operations
    _validate_skill_path(spec.skill_path)

    repo_url = f"https://github.com/{spec.owner}/{spec.repo}.git"

    with tempfile.TemporaryDirectory(prefix="skill-gather-") as tmp:
        tmp_path = Path(tmp)
        repo_dir = tmp_path / "repo"
        env = {**subprocess.os.environ, "GIT_TERMINAL_PROMPT": "0"}

        if spec.skill_path:
            _run_git(
                [
                    "clone", "--depth", "1", "-b", spec.branch,
                    "--filter=blob:none", "--sparse",
                    repo_url, str(repo_dir),
                ],
                env=env,
            )
            _run_git(["sparse-checkout", "set", spec.skill_path], cwd=repo_dir, env=env)
            source = repo_dir / spec.skill_path
            if not source.is_dir():
                raise FileNotFoundError(
                    f"Skill path not found in repository: {spec.skill_path}"
                )
            shutil.copytree(source, dest)
        else:
            _run_git(
                ["clone", "--depth", "1", "-b", spec.branch, repo_url, str(repo_dir)],
                env=env,
            )
            if (repo_dir / "SKILL.md").exists():
                shutil.copytree(repo_dir, dest, ignore=shutil.ignore_patterns(".git"))
            else:
                raise FileNotFoundError(
                    "Repository root has no SKILL.md — specify a skill subdirectory URL."
                )

    if not (dest / "SKILL.md").exists() and not (dest / "skill.md").exists():
        raise FileNotFoundError(f"Installed directory missing SKILL.md: {dest}")


def _install_from_skillhub(
    slug: str,
    target_dir: Path,
    dest: Path,
    *,
    force: bool,
) -> Path:
    """Install a SkillHub skill via the official skillhub CLI."""
    skillhub_bin = shutil.which("skillhub")
    if not skillhub_bin:
        raise RuntimeError(
            "SkillHub install requires the skillhub CLI.\n"
            "Install: curl -fsSL https://skillhub.cn/install/skillhub.md "
            "(see https://skillhub.cn for CLI setup)\n"
            f"Then run: skillhub install {slug} --dir {target_dir}"
        )

    if dest.exists():
        if not force:
            raise FileExistsError(
                f"Skill already exists at {dest} — use --force to overwrite."
            )
        shutil.rmtree(dest)

    cmd = [skillhub_bin, "install", slug, "--dir", str(target_dir)]
    if force:
        cmd.append("--force")

    logger.debug("Running: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"skillhub install failed: {stderr or exc}") from exc

    if dest.exists() and ((dest / "SKILL.md").exists() or (dest / "skill.md").exists()):
        return dest

    candidates = [
        p for p in target_dir.iterdir()
        if p.is_dir() and ((p / "SKILL.md").exists() or (p / "skill.md").exists())
    ]
    if len(candidates) == 1:
        if candidates[0] != dest:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.move(str(candidates[0]), str(dest))
        return dest

    raise FileNotFoundError(
        f"skillhub install completed but SKILL.md not found under {target_dir}. "
        f"Try: skillhub install {slug} --dir {target_dir}"
    )


def _run_git(
    args: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> None:
    cmd = ["git", *args]
    logger.debug("Running: %s", " ".join(cmd))
    try:
        subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError(
            "git is required for skill installation but was not found in PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"git failed: {stderr or exc}") from exc
