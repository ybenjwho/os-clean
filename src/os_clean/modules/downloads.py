"""Downloads cleanup module for os-clean.\n\nUses `dust` (preferred) or `du` fallback to list largest items.\nSupports multi-select + Archive / Purge / Skip with strong safety.\n"""

import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import questionary
from questionary import Choice

from ..disk import (
    SessionStats,
    get_disk_snapshot,
    get_path_size,
    human_size,
    run_df_full,
)
from ..ui import (
    console,
    print_error,
    print_header,
    print_info,
    print_success,
    print_warning,
    show_disk_snapshot,
    show_df_full,
)

TARGET = Path.home() / "Downloads"
ARCHIVE_ROOT = Path.home() / "Archive" / "Old_Downloads_2026"

# Matches leading size like "  84M", "1.2G", "819M" etc.
_SIZE_RE = re.compile(r"^\s*([\d.]+)\s*([KMGT]?)", re.IGNORECASE)


def _parse_size_to_bytes(size_str: str) -> int:
    """Convert dust/du style size (19M, 1.2G, 820K, etc) to integer bytes."""
    m = _SIZE_RE.match(size_str.strip())
    if not m:
        return 0
    val = float(m.group(1))
    unit = (m.group(2) or "").upper()
    mult = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}.get(unit, 1)
    return int(val * mult)


def get_largest_items(limit: int = 25) -> list[tuple[Path, int]]:
    """Return (path, size_in_bytes) for the largest direct children of TARGET.\n\n    Prefers `dust` (text output) when available for nice sizes; falls back to
    exact `du -b`. Always filters out the target directory itself.
    """
    if not TARGET.exists():
        return []

    # Preferred: dust text (very reliable output)
    try:
        cmd = ["dust", "-d", "1", str(limit), "-b", "-c", "--no-progress", str(TARGET)]
        out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
        items: list[tuple[Path, int]] = []
        for raw in out.splitlines():
            line = raw.strip()
            if not line or line.startswith("Indexing"):
                continue
            # Typical: " 33M   ├── some file.zip" or " 81M   ├── foo"
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            sz_str, rest = parts[0], parts[1]
            # Extract the final name after tree drawing chars
            # Examples of rest: "├── AWWA-....zip" or "┬─┴ Downloads"
            name = rest
            for marker in ("── ", "──", "└─ ", "├─ ", "┌─ ", "│ "):
                if marker in name:
                    name = name.split(marker, 1)[-1].strip()
                    break
            if not name:
                continue
            p = TARGET / name
            if p == TARGET or not p.exists():
                continue
            size = _parse_size_to_bytes(sz_str)
            items.append((p, size))
        if items:
            items.sort(key=lambda x: x[1], reverse=True)
            return items[:limit]
    except Exception:
        pass

    # Solid fallback: du gives exact byte counts
    try:
        cmd = f'du -b --max-depth=1 "{TARGET}" 2>/dev/null | sort -n | tail -n {limit}'
        out = subprocess.getoutput(cmd)
        items = []
        for line in out.strip().splitlines():
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) != 2:
                continue
            try:
                size = int(parts[0])
                p = Path(parts[1])
                if p != TARGET and p.parent == TARGET:
                    items.append((p, size))
            except ValueError:
                continue
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:limit]
    except Exception:
        return []


def _get_archive_dir() -> Path:
    """Create and return a timestamped archive directory for this run."""
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    archive_dir = ARCHIVE_ROOT / stamp
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


def _preview_operations(ops: list[tuple[Path, str, int]]) -> None:
    """Render a nice table of what is about to happen, with clear space impact."""
    from rich.table import Table

    table = Table(title="Planned Operations", show_header=True, header_style="bold yellow")
    table.add_column("Action", style="bold")
    table.add_column("Item")
    table.add_column("Size", justify="right")
    table.add_column("Space Freed Now", justify="right", style="green")

    total_arch = 0
    total_purge = 0
    will_free = 0

    for p, action, sz in ops:
        if action == "Archive":
            style = "cyan"
            freed_str = "0 B"
            total_arch += sz
        else:
            style = "red"
            freed_str = human_size(sz)
            total_purge += sz
            will_free += sz
        table.add_row(action, p.name, human_size(sz), freed_str, style=style)

    console.print(table)

    # Clear impact summary
    console.print()
    console.print(f"[cyan]To be archived (moved, space not freed yet):[/] {human_size(total_arch)}")
    console.print(f"[green]Will be purged (space freed immediately):[/] {human_size(total_purge)}")
    console.print(
        f"\n[bold green]→ Actual disk space that will be freed right now: {human_size(will_free)}[/]"
    )

    if total_arch > 0:
        console.print(
            "\n[yellow]Note:[/] Archived items are moved to "
            f"[cyan]{ARCHIVE_ROOT}[/cyan] (timestamped subfolders). "
            "You can review and purge them later for additional space."
        )
    console.print()


def clean_downloads(stats: SessionStats) -> None:
    """Interactive Downloads cleanup flow. Updates stats and shows disk impact."""
    print_header("Clean Downloads")

    if not TARGET.exists():
        print_warning(f"{TARGET} does not exist. Nothing to do.")
        return

    before = get_disk_snapshot()
    show_disk_snapshot(before, "Disk usage before Downloads cleanup")

    # Discover
    print_info(f"Scanning largest items under {TARGET} (using dust if available)...")
    items = get_largest_items(limit=25)

    if not items:
        print_info("No items found or all are hidden/empty. Nothing to clean.")
        return

    # Multi-select
    choices = [
        Choice(title=f"{human_size(sz):>10}  {p.name}", value=(p, sz))
        for p, sz in items
    ]

    selected = questionary.checkbox(
        "Select items to clean (↑↓ space to toggle, enter to confirm):",
        choices=choices,
    ).ask()

    if not selected:
        print_info("No items selected. Returning to menu.")
        return

    # Decide how to act on selection
    mode = questionary.select(
        "What action should we apply to the selected items?\n"
        "(Archive = move for later review — space not freed yet; Purge = delete now — space is freed)",
        choices=[
            "Archive all selected",
            "Purge all selected",
            "Decide for each item individually",
            "Cancel (go back)",
        ],
    ).ask()

    if mode is None or mode == "Cancel (go back)":
        print_info("Cancelled.")
        return

    ops: list[tuple[Path, str, int]] = []

    if mode == "Decide for each item individually":
        for p, sz in selected:
            action = questionary.select(
                f"Action for {p.name} ({human_size(sz)})?\n"
                "Archive = move (space not freed)   |   Purge = delete permanently (frees space now)",
                choices=["Archive", "Purge", "Skip"],
            ).ask()
            if action in ("Archive", "Purge"):
                ops.append((p, action, sz))
    else:
        action = "Archive" if "Archive" in mode else "Purge"
        for p, sz in selected:
            ops.append((p, action, sz))

    if not ops:
        print_info("No actions chosen (all skipped). Returning to menu.")
        return

    # Safety preview
    _preview_operations(ops)

    # Final confirmation
    proceed = questionary.confirm(
        "Proceed with the operations shown in the preview above?",
        default=False,
    ).ask()

    if not proceed:
        print_warning("Aborted by user. No changes made.")
        return

    # Extra confirmation for any purges
    purge_count = sum(1 for _, a, _ in ops if a == "Purge")
    if purge_count > 0:
        purge_confirm = questionary.text(
            f"Type 'PURGE' to permanently delete {purge_count} item(s) and free their space (or anything else to abort):",
            default="",
        ).ask()
        if (purge_confirm or "").strip().upper() != "PURGE":
            print_warning("Purge confirmation failed. Aborting all operations.")
            return

    # Execute
    archive_dir = _get_archive_dir()
    archived_count = 0
    purged_count = 0
    archived_bytes = 0
    purged_bytes = 0

    for p, action, sz in ops:
        try:
            if action == "Archive":
                dest = archive_dir / p.name
                # Avoid collision
                if dest.exists():
                    stem = p.stem
                    suffix = p.suffix
                    dest = archive_dir / f"{stem}_{datetime.now().strftime('%H%M%S')}{suffix}"
                shutil.move(str(p), str(dest))
                stats.add_archived(sz, dest)
                archived_count += 1
                archived_bytes += sz
                print_success(f"Archived: {p.name} → {dest}")
            else:  # Purge
                if p.is_dir():
                    shutil.rmtree(p, ignore_errors=False)
                else:
                    p.unlink()
                stats.add_purged(sz)
                purged_count += 1
                purged_bytes += sz
                print_success(f"Purged: {p.name}")
        except Exception as e:
            print_error(f"Failed to {action.lower()} {p.name}: {e}")

    # Results
    print()
    if archived_count or purged_count:
        print_success(
            f"Done. Freed {human_size(purged_bytes)} immediately by purging. "
            f"Archived {human_size(archived_bytes)} for later review."
        )
    else:
        print_info("No items were changed.")

    # Show impact
    print_info(f"Archive folder for this run: {archive_dir}")
    after = get_disk_snapshot()
    show_disk_snapshot(after, "Disk usage after Downloads cleanup")

    # Full picture
    console.print("\n[dim]Full df -h output after this module:[/dim]")
    show_df_full()

    # Quick hint
    if archived_count > 0:
        print_info("Tip: Review the archive folder later. You can purge from there when ready.")
