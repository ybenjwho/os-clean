"""Rich-based UI helpers for os-clean."""

from pathlib import Path
from typing import Iterable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .disk import DiskSnapshot, SessionStats, human_size, run_df_full

console = Console()


def print_welcome() -> None:
    """Display the welcome banner with a short onboarding explanation."""
    banner = Text()
    banner.append("os-clean", style="bold cyan")
    banner.append(" — Safe Linux Cleanup\n\n", style="dim")
    banner.append(
        "This tool helps you explore and recover disk space safely.\n"
        "We always show your disk usage before and after every action.\n\n"
        "Key concepts:\n"
        "  • Archive = move files to a review folder (space not freed yet)\n"
        "  • Purge   = permanently delete (space is freed immediately)\n"
        "  • Nothing is deleted without your explicit confirmation.",
        style="default",
    )

    panel = Panel(
        banner,
        title="[bold]Welcome[/]",
        border_style="cyan",
        padding=(1, 2),
    )
    console.print(panel)
    console.print()


def show_disk_snapshot(snapshot: DiskSnapshot, title: str = "Current Disk Usage") -> None:
    """Pretty print a single disk snapshot."""
    table = Table(title=title, show_header=True, header_style="bold magenta")
    table.add_column("Mount", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("Used", justify="right", style="red")
    table.add_column("Available", justify="right", style="green")
    table.add_column("Use %", justify="right")

    table.add_row(
        snapshot.mount,
        snapshot.total,
        snapshot.used,
        snapshot.avail,
        snapshot.use_pct,
    )
    console.print(table)
    console.print()


def show_df_full() -> None:
    """Show the full `df -h` output in a nice panel."""
    output = run_df_full()
    panel = Panel(
        f"[dim]{output}[/dim]",
        title="[bold]df -h[/]",
        border_style="blue",
        padding=(0, 1),
    )
    console.print(panel)
    console.print()


def show_session_summary(stats: SessionStats) -> None:
    """Show a prominent, encouraging final summary of the session."""
    title = "Session Summary"
    border = "green"

    if stats.total_recovered > 0:
        lines = []
        lines.append("[bold green]Excellent work! Here's what you accomplished:[/]\n")

        if stats.purged > 0:
            lines.append(f"[bold green]✓ Space freed immediately (purged):[/] {human_size(stats.purged)}")
        if stats.archived > 0:
            lines.append(f"[cyan]→ Moved to archive for later review:[/] {human_size(stats.archived)}")

        lines.append(f"\n[bold]Total impact this session:[/] {human_size(stats.total_recovered)}")

        if stats.archive_paths:
            lines.append("\n[bold]Your archives (review & purge when ready):[/]")
            for p in stats.archive_paths:
                lines.append(f"  • {p}")

        lines.append("\n[dim]Run os-clean again anytime — it's designed for iterative use.[/]")

        msg = "\n".join(lines)
    else:
        msg = (
            "[dim]No space was recovered in this session.[/]\n\n"
            "That's completely fine — sometimes a quick review is all that's needed.\n"
            "Come back whenever your disk feels full again!"
        )
        border = "blue"

    panel = Panel(
        msg,
        title=f"[bold]{title}[/]",
        border_style=border,
        padding=(1, 2),
    )
    console.print("\n")
    console.print(panel)


def confirm_action(message: str, default: bool = False) -> bool:
    """Simple yes/no confirmation using input (questionary will be used for complex choices)."""
    from rich.prompt import Confirm

    return Confirm.ask(message, default=default, console=console)


def print_info(message: str) -> None:
    console.print(f"[blue]ℹ[/] {message}")


def print_success(message: str) -> None:
    console.print(f"[green]✓[/] {message}")


def print_warning(message: str) -> None:
    console.print(f"[yellow]⚠[/] {message}")


def print_error(message: str) -> None:
    console.print(f"[red]✗[/] {message}")


def print_header(text: str) -> None:
    console.rule(f"[bold cyan]{text}[/]")


def format_file_list(paths: Iterable[Path], max_lines: int = 15) -> str:
    """Format a list of paths for display, limiting length."""
    items = list(paths)
    lines = []
    for p in items[:max_lines]:
        try:
            size = p.stat().st_size if p.is_file() else "dir"
            if isinstance(size, int):
                lines.append(f"  {p}  ({human_size(size)})")
            else:
                lines.append(f"  {p}/")
        except Exception:
            lines.append(f"  {p}")
    if len(items) > max_lines:
        lines.append(f"  ... and {len(items) - max_lines} more")
    return "\n".join(lines) if lines else "(none)"


def show_help() -> None:
    """Show a friendly explanation of the tool, its safety model, and Archive vs Purge."""
    print_header("About os-clean")

    console.print(
        "os-clean is an interactive tool that helps you safely free up disk space on Fedora (and similar Linux systems).\n"
    )

    console.print("[bold]How it works[/bold]")
    console.print("• Before every major action we show current disk usage (`df -h`).")
    console.print("• After the action we show the new usage so you can see the real impact.")
    console.print("• You stay in control at every step — nothing is ever deleted without confirmation.\n")

    console.print("[bold]Archive vs Purge (important!)[/bold]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Action", style="bold")
    table.add_column("What happens")
    table.add_column("Effect on disk space")
    table.add_row("Archive", "Moves files/folders to a timestamped review folder", "[yellow]No space freed yet[/yellow]")
    table.add_row("Purge", "Permanently deletes files/folders", "[green]Space is freed immediately[/green]")
    console.print(table)
    console.print()

    console.print("[bold]Safety principles[/bold]")
    console.print("• Prefer Archive first when you're unsure.")
    console.print("• Purging always requires an extra confirmation step (type PURGE for destructive actions).")
    console.print("• The tool is designed to be run iteratively — come back anytime.\n")

    console.print("[dim]Tip: Choose \"Help / About os-clean\" from the main menu whenever you want a refresher.[/dim]\n")

    console.print("[bold]Pro tip for elegant daily use[/bold]")
    console.print("Add one of these aliases to your shell config:")
    console.print("    alias oc='os-clean'")
    console.print("    alias clean='os-clean'")
    console.print("Then just type `oc` or `clean`.\n")
