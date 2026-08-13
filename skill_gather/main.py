"""Skill Store CLI.

Commands:
    sync    — crawl all (or specific) sources and update registry/
    stats   — print registry statistics
    list    — browse skills in a table
    show    — display one skill in detail
    search  — keyword search across the registry
    install — install a skill into a local agent directory
    export  — export registry to CSV or JSON
    daemon  — run sync on a schedule (blocking)
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from skill_gather.installer import DEFAULT_TARGETS, install_skill, resolve_target
from skill_gather.pipeline.run import run_pipeline
from skill_gather.registry_reader import find_skills, load_skills, search_skills
from skill_gather.registry_writer import (
    REGISTRY_DIR,
    export_csv,
    export_yaml,
    load_existing_skills,
    merge_skills_for_sources,
    write_registry,
)

console = Console()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=[RichHandler(console=console, show_path=False, markup=True)],
    )
    if not verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _load_registry() -> list[dict]:
    """Load skills from registry/skills.json. Exits if not found."""
    try:
        return load_skills()
    except FileNotFoundError:
        console.print("[red]Registry not found — run [bold]skill-gather sync[/bold] first.[/red]")
        sys.exit(1)


def _print_changelog(changelog: dict) -> None:
    """Print a human-readable diff summary."""
    s = changelog["summary"]
    if s["added"] == 0 and s["removed"] == 0 and s["modified"] == 0:
        console.print("[dim]No changes detected.[/dim]")
        return
    lines = []
    if s["added"]:
        lines.append(f"  [green]+{s['added']} added[/green]")
    if s["removed"]:
        lines.append(f"  [red]-{s['removed']} removed[/red]")
    if s["modified"]:
        lines.append(f"  [yellow]~{s['modified']} modified[/yellow]")
    console.print(Panel("\n".join(lines), title="Changes", border_style="dim"))

    # Show added / removed names (up to 10 each)
    if changelog["added"]:
        console.print("[green]Added:[/green]", "  ".join(changelog["added"][:10]),
                      "…" if len(changelog["added"]) > 10 else "")
    if changelog["removed"]:
        console.print("[red]Removed:[/red]", "  ".join(changelog["removed"][:10]),
                      "…" if len(changelog["removed"]) > 10 else "")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Skill Store — AI Agent Skill discovery engine and registry."""
    _load_env()
    _setup_logging(verbose)
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose


# ---------------------------------------------------------------------------
# sync
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--source", "-s",
    multiple=True,
    help="Sync only specific source IDs (repeatable).",
)
@click.option("--dry-run", is_flag=True, help="Run pipeline without writing files.")
@click.option("--force", is_flag=True, help="Re-sync all sources even if upstream is unchanged.")
@click.option(
    "--no-incremental",
    is_flag=True,
    help="Disable upstream fingerprint skip (always crawl every source).",
)
@click.pass_context
def sync(
    ctx: click.Context,
    source: tuple[str, ...],
    dry_run: bool,
    force: bool,
    no_incremental: bool,
) -> None:
    """Fetch skills from sources and update the registry."""
    source_ids = list(source) or None
    label = ", ".join(source_ids) if source_ids else "all enabled sources"
    console.print(f"[bold]Syncing:[/bold] {label}")

    started = datetime.now(timezone.utc)
    existing = load_existing_skills()
    result = run_pipeline(
        source_ids=source_ids,
        existing_skills=existing or None,
        force=force,
        incremental=not no_incremental,
    )
    skills = result.skills

    if not skills:
        if existing and result.skipped_sources:
            console.print(
                "[green]✓[/green] All sources unchanged — registry is up to date."
            )
            return
        console.print("[yellow]No skills collected — check logs above.[/yellow]")
        sys.exit(1)

    if result.skipped_sources:
        console.print(
            f"[dim]Incremental skip ({len(result.skipped_sources)}): "
            f"{', '.join(result.skipped_sources)}[/dim]"
        )

    if source_ids:
        existing = load_existing_skills()
        if existing:
            skills = merge_skills_for_sources(existing, skills, set(source_ids))
            console.print(
                f"[dim]Merged partial sync → [bold]{len(skills)}[/bold] total skills in registry[/dim]"
            )

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    console.print(
        f"\n[green]✓[/green] Collected [bold]{len(skills)}[/bold] skills "
        f"in {elapsed:.1f}s"
    )

    if dry_run:
        console.print("[yellow]Dry-run — skipping registry write.[/yellow]")
        return

    changelog = write_registry(
        skills,
        source_fingerprints=result.source_fingerprints,
        skipped_sources=set(result.skipped_sources),
        synced_sources=set(result.synced_sources),
    )
    _print_changelog(changelog)
    console.print(f"[green]✓[/green] Registry updated at [bold]{REGISTRY_DIR}[/bold]")


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

@cli.command()
def stats() -> None:
    """Print statistics from the current registry."""
    meta_path = REGISTRY_DIR / "meta.json"
    if not meta_path.exists():
        console.print("[red]Registry not found — run [bold]skill-gather sync[/bold] first.[/red]")
        sys.exit(1)

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    console.print()
    console.print(Panel(
        f"[bold]{meta['total_skills']}[/bold] skills across "
        f"[bold]{meta['sources_count']}[/bold] sources\n"
        f"Last synced: [dim]{meta.get('last_synced', 'unknown')}[/dim]",
        title="[bold]Skill Store Registry[/bold]",
        border_style="cyan",
    ))

    # By category
    console.print("\n[bold cyan]By Category[/bold cyan]")
    cat_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    cat_table.add_column("Category", style="cyan")
    cat_table.add_column("Count", justify="right")
    cat_table.add_column("Bar")
    total = meta["total_skills"] or 1
    for cat, count in sorted(meta["categories"].items(), key=lambda x: -x[1]):
        bar = "█" * max(1, round(count / total * 30))
        cat_table.add_row(cat, str(count), f"[dim]{bar}[/dim]")
    console.print(cat_table)

    # By source
    console.print("\n[bold cyan]By Source[/bold cyan]")
    src_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    src_table.add_column("Source ID", style="green")
    src_table.add_column("Count", justify="right")
    for src, count in sorted(meta.get("source_counts", {}).items(), key=lambda x: -x[1]):
        src_table.add_row(src, str(count))
    console.print(src_table)

    # Platform compat
    console.print("\n[bold cyan]Platform Compatibility[/bold cyan]")
    plat_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    plat_table.add_column("Platform", style="magenta")
    plat_table.add_column("Count", justify="right")
    for plat, count in meta.get("platform_counts", {}).items():
        plat_table.add_row(plat, str(count))
    console.print(plat_table)

    # Score distribution
    console.print("\n[bold cyan]Score Distribution[/bold cyan]")
    for bucket, count in meta.get("score_distribution", {}).items():
        bar = "█" * min(count, 40)
        console.print(f"  [dim]{bucket:8s}[/dim]  [yellow]{bar}[/yellow] {count}")

    # Last changelog
    cl = meta.get("changelog")
    if cl and any(cl.values()):
        console.print(
            f"\n[dim]Last sync changes: "
            f"+{cl.get('added',0)} / -{cl.get('removed',0)} / ~{cl.get('modified',0)}[/dim]"
        )
    console.print()


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

@cli.command("list")
@click.option("--source", "-s", default=None, help="Filter by source ID.")
@click.option("--category", "-c", default=None, help="Filter by category.")
@click.option("--platform", "-p",
              type=click.Choice(["claude_code", "claude_ai", "kiro", "codex", "universal"]),
              default=None, help="Filter by platform compatibility.")
@click.option("--min-score", default=0, help="Minimum quality score (0-100).")
@click.option("--limit", "-n", default=50, show_default=True, help="Max rows to show.")
def list_skills(
    source: str | None,
    category: str | None,
    platform: str | None,
    min_score: int,
    limit: int,
) -> None:
    """Browse skills in a table view."""
    skills = _load_registry()

    if source:
        skills = [s for s in skills if s["discovery"]["source_id"] == source]
    if category:
        skills = [s for s in skills if s["category"] == category]
    if platform:
        skills = [s for s in skills if s.get("platform", {}).get(platform)]
    if min_score:
        skills = [s for s in skills if s.get("score", 0) >= min_score]

    total_filtered = len(skills)
    skills = skills[:limit]

    table = Table(show_header=True, header_style="bold green", box=None, padding=(0, 1))
    table.add_column("#",          style="dim",   width=4)
    table.add_column("Skill ID",   style="green", no_wrap=True, max_width=40)
    table.add_column("Category",   style="cyan",  width=13)
    table.add_column("Score",      justify="right", width=6)
    table.add_column("★ Stars",    justify="right", width=7)
    table.add_column("Platforms",  width=28)
    table.add_column("Description", max_width=55)

    for i, skill in enumerate(skills, start=1):
        plats = [k for k, v in skill.get("platform", {}).items() if v]
        table.add_row(
            str(i),
            skill["skill_id"],
            skill.get("category", "other"),
            str(skill.get("score", 0)),
            str(skill["signals"].get("repo_stars", 0)),
            " ".join(plats),
            (skill["spec"].get("description") or "")[:100],
        )

    console.print(table)
    console.print(
        f"\n[dim]Showing {len(skills)} of {total_filtered} matching skills "
        f"(total in registry: use --limit to see more)[/dim]\n"
    )


# ---------------------------------------------------------------------------
# show
# ---------------------------------------------------------------------------

def _format_platforms(platform: dict) -> str:
    return ", ".join(name for name, enabled in platform.items() if enabled) or "—"


def _print_skill_detail(skill: dict) -> None:
    spec = skill.get("spec", {})
    discovery = skill.get("discovery", {})
    signals = skill.get("signals", {})
    platform = skill.get("platform", {})

    console.print()
    console.print(Panel(
        f"[bold green]{skill['skill_id']}[/bold green]\n"
        f"[cyan]{spec.get('name', '')}[/cyan]  ·  score [bold]{skill.get('score', 0)}[/bold]  ·  "
        f"{skill.get('category', 'other')}",
        title="Skill",
        border_style="green",
    ))

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Field", style="dim", width=16)
    table.add_column("Value")
    table.add_row("Description", spec.get("description") or "—")
    table.add_row("License", spec.get("license") or "—")
    table.add_row("Compatibility", spec.get("compatibility") or "—")
    table.add_row("Source", discovery.get("source_id", "—"))
    table.add_row("Source URL", discovery.get("source_url", "—"))
    table.add_row("Install URL", discovery.get("install_url", "—"))
    table.add_row("Path", discovery.get("source_path") or "—")
    table.add_row("Platforms", _format_platforms(platform))
    table.add_row("Stars", str(signals.get("repo_stars", 0)))
    table.add_row("Installs", str(signals.get("install_count", 0)))
    table.add_row("Scripts", "yes" if signals.get("has_scripts") else "no")
    table.add_row("References", "yes" if signals.get("has_references") else "no")
    table.add_row("Tags", ", ".join(skill.get("tags", [])) or "—")
    console.print(table)
    console.print()


@cli.command()
@click.argument("query")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON.")
def show(query: str, as_json: bool) -> None:
    """Show full details for a skill (by skill_id or name)."""
    matches = find_skills(query)
    if not matches:
        console.print(f"[red]No skill found matching[/red] [bold]{query}[/bold]")
        sys.exit(1)

    if len(matches) > 1 and not as_json:
        console.print(f"[yellow]{len(matches)} matches for[/yellow] [bold]{query}[/bold]:")
        for skill in matches:
            console.print(f"  [green]{skill['skill_id']}[/green]  [dim]score={skill.get('score', 0)}[/dim]")
        console.print("\n[dim]Be more specific, e.g. skill-gather show anthropics/skills/mcp-builder[/dim]")
        sys.exit(1)

    skill = matches[0]
    if as_json:
        console.print(json.dumps(skill, ensure_ascii=False, indent=2))
        return
    _print_skill_detail(skill)


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query", default="")
@click.option("--source", "-s", default=None, help="Filter by source ID.")
@click.option("--category", "-c", default=None, help="Filter by category.")
@click.option("--platform", "-p",
              type=click.Choice(["claude_code", "claude_ai", "kiro", "codex", "universal"]),
              default=None, help="Filter by platform compatibility.")
@click.option("--min-score", default=0, help="Minimum quality score (0-100).")
@click.option("--limit", "-n", default=20, show_default=True, help="Max rows to show.")
def search(
    query: str,
    source: str | None,
    category: str | None,
    platform: str | None,
    min_score: int,
    limit: int,
) -> None:
    """Search skills by keywords (name, description, tags)."""
    skills = search_skills(
        query,
        source=source,
        category=category,
        platform=platform,
        min_score=min_score,
        limit=limit,
    )

    if not skills:
        console.print("[yellow]No skills matched your query.[/yellow]")
        sys.exit(1)

    table = Table(show_header=True, header_style="bold magenta", box=None, padding=(0, 1))
    table.add_column("#", style="dim", width=4)
    table.add_column("Skill ID", style="green", max_width=42)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Source", width=18)
    table.add_column("Description", max_width=50)

    for i, skill in enumerate(skills, start=1):
        table.add_row(
            str(i),
            skill["skill_id"],
            str(skill.get("score", 0)),
            skill.get("discovery", {}).get("source_id", ""),
            (skill.get("spec", {}).get("description") or "")[:80],
        )

    console.print(table)
    console.print(f"\n[dim]{len(skills)} result(s)[/dim]\n")


# ---------------------------------------------------------------------------
# install
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("query")
@click.option(
    "--target", "-t",
    default=None,
    help="Destination directory (default: ~/.cursor/skills).",
)
@click.option(
    "--preset", "-p",
    type=click.Choice(sorted(DEFAULT_TARGETS.keys())),
    default="cursor",
    show_default=True,
    help="Built-in install target preset.",
)
@click.option("--force", is_flag=True, help="Overwrite an existing installation.")
def install(query: str, target: str | None, preset: str, force: bool) -> None:
    """Install a skill from its registry install_url.

    Requires git. Supports GitHub tree URLs such as:
    https://github.com/owner/repo/tree/main/skills/my-skill
    """
    matches = find_skills(query)
    if not matches:
        console.print(f"[red]No skill found matching[/red] [bold]{query}[/bold]")
        sys.exit(1)
    if len(matches) > 1:
        console.print(f"[yellow]{len(matches)} matches for[/yellow] [bold]{query}[/bold]:")
        for skill in matches:
            console.print(f"  [green]{skill['skill_id']}[/green]")
        console.print("\n[dim]Be more specific before installing.[/dim]")
        sys.exit(1)

    skill = matches[0]
    dest_root = resolve_target(target, preset=None if target else preset)

    console.print(
        f"[bold]Installing[/bold] [green]{skill['skill_id']}[/green]\n"
        f"  → [dim]{dest_root}[/dim]"
    )

    try:
        dest = install_skill(skill, dest_root, force=force)
    except FileExistsError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        sys.exit(1)
    except (ValueError, RuntimeError, FileNotFoundError) as exc:
        console.print(f"[red]Install failed:[/red] {exc}")
        install_url = skill.get("discovery", {}).get("install_url", "")
        if install_url:
            console.print(f"[dim]Manual install URL: {install_url}[/dim]")
        sys.exit(1)

    console.print(f"[green]✓[/green] Installed to [bold]{dest}[/bold]")
    console.print("[dim]Restart your agent session to pick up the new skill.[/dim]")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("output", type=click.Path())
@click.option(
    "--format", "-f",
    "fmt",
    type=click.Choice(["csv", "json", "yaml"]),
    default="csv",
    show_default=True,
    help="Output format.",
)
@click.option("--source", "-s", default=None, help="Filter by source ID before export.")
@click.option("--category", "-c", default=None, help="Filter by category before export.")
@click.option("--min-score", default=0, help="Minimum score filter.")
def export(
    output: str,
    fmt: str,
    source: str | None,
    category: str | None,
    min_score: int,
) -> None:
    """Export registry to CSV or JSON.

    Examples:\n
        skill-gather export skills.csv\n
        skill-gather export skills.json --format json\n
        skill-gather export dev.csv --category development
    """
    skills = _load_registry()

    if source:
        skills = [s for s in skills if s["discovery"]["source_id"] == source]
    if category:
        skills = [s for s in skills if s["category"] == category]
    if min_score:
        skills = [s for s in skills if s.get("score", 0) >= min_score]

    out_path = Path(output)

    if fmt == "csv":
        export_csv(skills, out_path)
    elif fmt == "yaml":
        export_yaml(skills, out_path)
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(
                {"skills": skills, "total": len(skills),
                 "exported_at": datetime.now(timezone.utc).isoformat()},
                f, ensure_ascii=False, indent=2,
            )

    console.print(
        f"[green]✓[/green] Exported [bold]{len(skills)}[/bold] skills "
        f"to [bold]{out_path}[/bold] ({fmt.upper()})"
    )


# ---------------------------------------------------------------------------
# daemon
# ---------------------------------------------------------------------------

@cli.command()
@click.option(
    "--interval", "-i",
    default=24,
    show_default=True,
    help="Sync interval in hours.",
)
@click.option(
    "--source", "-s",
    multiple=True,
    help="Sync only specific source IDs (repeatable).",
)
def daemon(interval: int, source: tuple[str, ...]) -> None:
    """Run sync on a recurring schedule (blocking).

    Executes an immediate sync on startup, then repeats every INTERVAL hours.
    Send SIGINT (Ctrl-C) or SIGTERM to stop.
    """
    import signal

    source_ids = list(source) or None
    interval_secs = interval * 3600
    _stop = False

    def _handle_signal(signum: int, frame: object) -> None:
        nonlocal _stop
        console.print(f"\n[bold]Received signal {signum} — stopping after current run.[/bold]")
        _stop = True

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    console.print(
        f"[bold]Daemon started[/bold] — syncing every [bold]{interval}h[/bold]. "
        f"Press Ctrl-C to stop."
    )

    run_count = 0
    while not _stop:
        run_count += 1
        console.print(f"\n[dim][Run #{run_count} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][/dim]")

        try:
            existing = load_existing_skills()
            result = run_pipeline(
                source_ids=source_ids,
                existing_skills=existing or None,
            )
            skills = result.skills
            if skills:
                if source_ids and existing:
                    skills = merge_skills_for_sources(existing, skills, set(source_ids))
                changelog = write_registry(
                    skills,
                    source_fingerprints=result.source_fingerprints,
                    skipped_sources=set(result.skipped_sources),
                    synced_sources=set(result.synced_sources),
                )
                _print_changelog(changelog)
                console.print(
                    f"[green]✓[/green] Sync complete — "
                    f"[bold]{len(skills)}[/bold] skills in registry."
                )
            elif existing and result.skipped_sources:
                console.print("[dim]All sources unchanged this run.[/dim]")
            else:
                console.print("[yellow]Warning: no skills collected this run.[/yellow]")
        except Exception as e:
            console.print(f"[red]Sync failed: {e}[/red]")
            logging.getLogger(__name__).exception("Daemon sync error")

        if _stop:
            break

        next_run = datetime.now()
        next_ts = next_run.timestamp() + interval_secs
        console.print(
            f"[dim]Next run at "
            f"{datetime.fromtimestamp(next_ts).strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        )

        # Sleep in small chunks so SIGTERM/SIGINT wakes us promptly
        deadline = time.monotonic() + interval_secs
        try:
            while not _stop and time.monotonic() < deadline:
                time.sleep(min(5.0, deadline - time.monotonic()))
        except KeyboardInterrupt:
            _stop = True

    console.print("[bold]Daemon stopped.[/bold]")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
