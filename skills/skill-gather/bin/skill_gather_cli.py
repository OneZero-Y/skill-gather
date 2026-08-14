#!/usr/bin/env python3
"""Cross-platform entry point for the skill-gather skill.

This wrapper exists because a SKILL.md is read by an agent, not executed as a
shell script. The agent issues one command at a time, on an unknown OS, from an
unknown working directory. Shell-specific constructs (`$(dirname "$0")`,
`if [ -n "$VAR" ]`) break on Windows PowerShell and cmd, so every piece of
logic that would otherwise live in shell lives here instead.

Responsibilities:
  1. Locate the skill root from this file's own path, so the caller's working
     directory does not matter.
  2. Bootstrap dependencies into a private .venv on first use, preferring uv
     and falling back to stdlib venv + pip.
  3. Re-exec under that .venv so the real CLI runs with its dependencies.
  4. Provide an `update` command that only syncs when a GitHub token is present,
     and explains what to do when it is not.
  5. Forward every other command straight through to the skill-gather CLI.

Usage (identical on Windows, macOS and Linux):

    python bin/skill_gather_cli.py doctor
    python bin/skill_gather_cli.py search "excel" --limit 5
    python bin/skill_gather_cli.py update
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SKILL_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = SKILL_ROOT / ".venv"
REGISTRY_SOURCES = SKILL_ROOT / "registry" / "sources"

# Set when we re-exec into the venv, so a broken venv cannot cause a fork bomb.
_REEXEC_FLAG = "SKILL_GATHER_BOOTSTRAPPED"

# Packages that must be importable for the CLI to run. Checked by import name,
# which differs from the distribution name for some of these.
_REQUIRED_MODULES = ("httpx", "pydantic", "yaml", "rich", "click", "dotenv")


def venv_python() -> Path:
    """Path to the interpreter inside our private venv, per-platform."""
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


# ---------------------------------------------------------------------------
# Output helpers
#
# Deliberately plain text with stable prefixes: the consumer is an agent
# parsing stdout, not a human reading a styled terminal.
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    print(f"[skill-gather] {msg}", flush=True)


def error(msg: str) -> None:
    print(f"[skill-gather] ERROR: {msg}", file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Dependency bootstrap
# ---------------------------------------------------------------------------

def deps_available() -> bool:
    """True when every required dependency can be imported right now."""
    from importlib.util import find_spec

    for module in _REQUIRED_MODULES:
        try:
            if find_spec(module) is None:
                return False
        except (ImportError, ValueError):
            return False
    return True


def _run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


def _bootstrap_with_uv() -> bool:
    """Create the venv and install dependencies using uv. Returns success."""
    uv = shutil.which("uv")
    if not uv:
        return False

    info("Installing dependencies with uv (first run only)...")
    result = _run([uv, "sync", "--no-dev"], cwd=SKILL_ROOT)
    if result.returncode == 0 and venv_python().exists():
        info("Dependencies installed.")
        return True

    info("uv sync did not succeed; falling back to venv + pip.")
    if result.stderr.strip():
        info(f"uv output: {result.stderr.strip()[:400]}")
    return False


def _bootstrap_with_pip() -> bool:
    """Create the venv and install dependencies using stdlib venv + pip."""
    requirements = SKILL_ROOT / "requirements.txt"
    if not requirements.exists():
        error(
            f"Cannot install dependencies: {requirements} is missing and uv is "
            "unavailable. Install uv (https://docs.astral.sh/uv/) and retry."
        )
        return False

    if not venv_python().exists():
        info("Creating virtual environment...")
        result = _run([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=SKILL_ROOT)
        if result.returncode != 0:
            error(f"Failed to create venv: {result.stderr.strip()[:400]}")
            return False

    info("Installing dependencies with pip (first run only)...")
    result = _run(
        [str(venv_python()), "-m", "pip", "install", "--quiet",
         "-r", str(requirements)],
        cwd=SKILL_ROOT,
    )
    if result.returncode != 0:
        error(f"pip install failed: {result.stderr.strip()[:600]}")
        return False

    info("Dependencies installed.")
    return True


def _running_in_skill_venv() -> bool:
    """True when the current interpreter is running out of our private venv.

    Compares sys.prefix against the venv directory rather than comparing
    interpreter paths. On POSIX, .venv/bin/python is a symlink to the base
    interpreter, so resolving both sides makes a system interpreter look
    identical to the venv one — which sent every second invocation down the
    "already inside the venv" branch and made it install into the wrong
    environment. sys.prefix is the venv directory for a venv interpreter and
    the base installation otherwise (PEP 405), which is unambiguous.
    """
    try:
        return Path(sys.prefix).resolve() == VENV_DIR.resolve()
    except OSError:
        return False


def _reexec(python: Path) -> None:
    """Re-run this command under `python` and exit with its status."""
    env = dict(os.environ, **{_REEXEC_FLAG: "1"})
    completed = subprocess.run(
        [str(python), str(Path(__file__).resolve()), *sys.argv[1:]],
        env=env,
    )
    sys.exit(completed.returncode)


def ensure_dependencies() -> None:
    """Make dependencies importable, re-execing into the private venv if needed.

    The agent invokes this wrapper with whatever `python` is on PATH, which is
    usually not the venv interpreter. So the common case is: dependencies are
    missing *for the current interpreter* while the venv is already complete.
    Handing off to the venv directly in that case matters — otherwise every
    single command would re-run the installer and print bootstrap noise.
    """
    if deps_available():
        return

    guard = os.environ.get(_REEXEC_FLAG) == "1"
    in_venv = _running_in_skill_venv()

    # Fast path: a venv already exists and we are not it. Hand off without
    # running the installer; that process re-runs this check and will bootstrap
    # in place if the venv turns out to be incomplete.
    if not in_venv and not guard and venv_python().exists():
        _reexec(venv_python())

    if guard and not in_venv:
        error(
            "Bootstrap did not produce a usable environment. Install manually:\n"
            f"  cd {SKILL_ROOT}\n"
            "  uv sync --no-dev      (or: pip install -r requirements.txt)"
        )
        sys.exit(1)

    # Either there is no venv yet, or we are running from an incomplete one.
    if not (_bootstrap_with_uv() or _bootstrap_with_pip()):
        sys.exit(1)

    if in_venv:
        # We just installed into the environment we are already running in.
        import importlib

        importlib.invalidate_caches()
        if deps_available():
            return
        error(
            "Dependencies still missing after installing into the active "
            f"environment ({sys.executable}). Try removing {VENV_DIR} and retrying."
        )
        sys.exit(1)

    python = venv_python()
    if not python.exists():
        error(f"Expected interpreter not found after bootstrap: {python}")
        sys.exit(1)

    _reexec(python)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def github_token() -> str | None:
    """Resolve a GitHub token from the environment or a local .env file.

    Only the presence of a token is ever reported; the value is never printed.
    """
    for var in ("GITHUB_TOKEN", "GH_TOKEN", "SKILL_GATHER_GITHUB_TOKEN"):
        value = os.environ.get(var, "").strip()
        if value:
            return value

    env_file = SKILL_ROOT / ".env"
    if env_file.exists():
        try:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                if key.strip() in ("GITHUB_TOKEN", "GH_TOKEN"):
                    value = value.strip().strip("'\"")
                    if value:
                        return value
        except OSError:
            pass

    return None


def _load_meta() -> dict:
    meta_file = SKILL_ROOT / "registry" / "meta.json"
    if not meta_file.exists():
        return {}
    try:
        import json

        return json.loads(meta_file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def snapshot_summary() -> str:
    """One-line description of the bundled registry snapshot."""
    meta = _load_meta()
    if not meta:
        return "no registry snapshot found"

    total = meta.get("total_skills", "?")
    sources = meta.get("sources_count", "?")
    synced = str(meta.get("last_synced", "unknown"))[:19].replace("T", " ")
    summary = f"{total} skills from {sources} sources, snapshot taken {synced} UTC"

    # The shipped snapshot is a curated subset, since marketplaces cap file
    # size. Saying so matters: otherwise a search that misses looks like the
    # skill does not exist anywhere, when running `update` would find it.
    bundle = meta.get("bundle") or {}
    if bundle.get("is_subset"):
        full = bundle.get("full_registry_total")
        coverage = bundle.get("coverage_pct")
        if full:
            summary += f" (curated subset: {coverage}% of {full} in the full registry)"
    return summary


def cmd_doctor() -> int:
    """Report environment readiness without changing anything."""
    info(f"Skill root       : {SKILL_ROOT}")
    info(f"Python           : {sys.version.split()[0]} ({sys.executable})")
    info(f"Dependencies     : {'ready' if deps_available() else 'not installed'}")
    info(f"Registry data    : {snapshot_summary()}")

    shard_count = len(list(REGISTRY_SOURCES.glob('*.json'))) if REGISTRY_SOURCES.exists() else 0
    info(f"Registry shards  : {shard_count}")

    has_token = github_token() is not None
    info(f"GitHub token     : {'configured' if has_token else 'not configured'}")

    is_subset = (_load_meta().get("bundle") or {}).get("is_subset")
    if is_subset and has_token:
        info("  Run `update` to replace the curated subset with the full registry.")
    elif not has_token:
        info(
            "  Without a token, `update` is skipped and the bundled snapshot is "
            "used. To enable updates, set GITHUB_TOKEN in your environment."
        )

    git_available = shutil.which("git") is not None
    info(f"git              : {'available' if git_available else 'NOT FOUND'}")
    if not git_available:
        info("  `install` requires git. Install it from https://git-scm.com/")

    if shard_count == 0:
        error("No registry data available. Run `update` with a GitHub token.")
        return 1
    return 0


def cmd_update(extra_args: list[str]) -> int:
    """Refresh the registry from upstream, but only when a token is present.

    Syncing without a token hits GitHub's 60 requests/hour anonymous limit and
    reliably fails partway through, which would leave the registry in a worse
    state than the bundled snapshot. So the absence of a token is treated as a
    clean skip rather than an attempt.
    """
    if github_token() is None:
        info("No GitHub token configured — skipping update.")
        info(f"Using bundled snapshot: {snapshot_summary()}")
        info("")
        info("To enable updates, set a token with public repo read access:")
        if os.name == "nt":
            info('  PowerShell:  $env:GITHUB_TOKEN = "ghp_xxxx"')
            info("  cmd:         set GITHUB_TOKEN=ghp_xxxx")
        else:
            info("  export GITHUB_TOKEN=ghp_xxxx")
        info("Create one at https://github.com/settings/tokens")
        # Not an error: the skill remains fully usable on the snapshot.
        return 0

    info("GitHub token detected — syncing registry from upstream.")
    info("This can take several minutes across all sources.")

    # Make the token visible under the name the adapters read.
    os.environ.setdefault("GITHUB_TOKEN", github_token() or "")

    code = run_cli(["sync", *extra_args])
    if code == 0:
        info(f"Registry updated: {snapshot_summary()}")
    else:
        error(
            "Sync failed. The previous snapshot is still in place, so search "
            "and install continue to work on the older data."
        )
    return code


def run_cli(args: list[str]) -> int:
    """Invoke the skill-gather Click CLI in-process."""
    if str(SKILL_ROOT) not in sys.path:
        sys.path.insert(0, str(SKILL_ROOT))

    try:
        from skill_gather.main import cli
    except ImportError as exc:
        error(
            f"Could not import skill_gather ({exc}). "
            "Run `python bin/skill_gather_cli.py doctor` to diagnose."
        )
        return 1

    try:
        # standalone_mode=False stops Click from calling sys.exit itself, so we
        # can return the code and keep our own reporting around the call.
        cli.main(args=args, standalone_mode=False)
        return 0
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:  # noqa: BLE001 — surface any CLI failure verbatim
        error(f"{type(exc).__name__}: {exc}")
        return 1


USAGE = """skill-gather — AI agent skill discovery

Usage: python bin/skill_gather_cli.py <command> [options]

Commands:
  doctor                    Check environment, data and token status
  update                    Refresh registry (requires GITHUB_TOKEN)
  search <query> [options]  Search skills by keyword
  show <skill_id>           Show full details for one skill
  list [options]            Browse skills by category/platform/source
  install <skill_id>        Install a skill into an agent directory
  stats                     Registry totals and category breakdown

Run any command with --help for its options.
"""


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    if not args or args[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0

    command, rest = args[0], args[1:]

    # doctor must work before dependencies exist, since diagnosing a failed
    # bootstrap is exactly when it is needed.
    if command == "doctor":
        return cmd_doctor()

    ensure_dependencies()

    if command == "update":
        return cmd_update(rest)

    return run_cli([command, *rest])


if __name__ == "__main__":
    sys.exit(main())
