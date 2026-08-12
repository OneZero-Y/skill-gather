"""Skill Store CLI.

Commands:
    sync    — crawl all (or specific) sources and update registry/
    stats   — print registry statistics
    list    — browse skills in a table
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

from skill_store.pipeline.run import run_pipeline
from skill_store.registry_writer import REGISTRY_DIR, export_csv, write_registry

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
    path = REGISTRY_DIR / "skills.json"
    if not path.exists():
        console.print("[red]Registry not found — run [bold]skill-store sync[/bold] first.[/red]")
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)["skills"]


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
@click.pass_context
def sync(ctx: click.Context, source: tuple[str, ...], dry_run: bool) -> None:
    """Fetch skills from sources and update the registry."""
    source_ids = list(source) or None
    label = ", ".join(source_ids) if source_ids else "all enabled sources"
    console.print(f"[bold]Syncing:[/bold] {label}")

    started = datetime.now(timezone.utc)
    skills = run_pipeline(source_ids=source_ids)

    if not skills:
        console.print("[yellow]No skills collected — check logs above.[/yellow]")
        sys.exit(1)

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    console.print(
        f"\n[green]✓[/green] Collected [bold]{len(skills)}[/bold] skills "
        f"in {elapsed:.1f}s"
    )

    if dry_run:
        console.print("[yellow]Dry-run — skipping registry write.[/yellow]")
        return

    changelog = write_registry(skills)
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
        console.print("[red]Registry not found — run [bold]skill-store sync[/bold] first.[/red]")
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
# export
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("output", type=click.Path())
@click.option(
    "--format", "-f",
    "fmt",
    type=click.Choice(["csv", "json"]),
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
        skill-store export skills.csv\n
        skill-store export skills.json --format json\n
        skill-store export dev.csv --category development
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
    Send SIGINT (Ctrl-C) to stop.
    """
    source_ids = list(source) or None
    interval_secs = interval * 3600

    console.print(
        f"[bold]Daemon started[/bold] — syncing every [bold]{interval}h[/bold]. "
        f"Press Ctrl-C to stop."
    )

    run_count = 0
    while True:
        run_count += 1
        console.print(f"\n[dim][Run #{run_count} — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}][/dim]")

        try:
            skills = run_pipeline(source_ids=source_ids)
            if skills:
                changelog = write_registry(skills)
                _print_changelog(changelog)
                console.print(
                    f"[green]✓[/green] Sync complete — "
                    f"[bold]{len(skills)}[/bold] skills in registry."
                )
            else:
                console.print("[yellow]Warning: no skills collected this run.[/yellow]")
        except Exception as e:
            console.print(f"[red]Sync failed: {e}[/red]")
            logging.getLogger(__name__).exception("Daemon sync error")

        next_run = datetime.now()
        next_ts = next_run.timestamp() + interval_secs
        console.print(
            f"[dim]Next run at "
            f"{datetime.fromtimestamp(next_ts).strftime('%Y-%m-%d %H:%M:%S')}[/dim]"
        )

        try:
            time.sleep(interval_secs)
        except KeyboardInterrupt:
            console.print("\n[bold]Daemon stopped.[/bold]")
            break


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
