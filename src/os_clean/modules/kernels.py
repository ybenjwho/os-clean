"""Clean Old Kernels module for os-clean.\n\nUses Fedora's official dnf \"installonly\" mechanism (`--oldinstallonly` + `installonly_limit`)\nto safely remove old kernel packages. The running kernel is always protected by dnf.\n"""

import re
import subprocess

import questionary

from ..disk import SessionStats, get_disk_snapshot, human_size
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


def _get_running_kernel() -> str:
    """Return the currently running kernel version string (e.g. 7.0.12-201.fc44.x86_64)."""
    try:
        return subprocess.getoutput("uname -r").strip()
    except Exception:
        return ""


def _get_installonly_packages() -> list[str]:
    """Return full list of currently installed installonly packages."""
    try:
        result = subprocess.run(
            ["dnf", "repoquery", "--installonly", "--qf", "%{name}-%{evr}.%{arch}"],
            capture_output=True,
            text=True,
            check=False,
        )
        raw = result.stdout or ""
        # dnf normally emits one per line; be robust against capture quirks
        parts = re.split(r'(?=kernel-)', raw)
        return [p.strip() for p in parts if p.strip().startswith("kernel-")]
    except Exception:
        return []


def _get_packages_to_remove(keep: int) -> list[str]:
    """Return the exact packages dnf would remove when configured to keep the latest `keep` installonly packages."""
    if keep < 1:
        return []
    try:
        result = subprocess.run(
            ["dnf", "repoquery", "--installonly", f"--latest-limit=-{keep}", "--qf", "%{name}-%{evr}.%{arch}"],
            capture_output=True,
            text=True,
            check=False,
        )
        raw = result.stdout or ""
        parts = re.split(r'(?=kernel-)', raw)
        return [p.strip() for p in parts if p.strip().startswith("kernel-")]
    except Exception:
        return []


def _get_package_size(pkg: str) -> int:
    """Return installed size in bytes for a package (via rpm)."""
    try:
        result = subprocess.run(
            ["rpm", "-q", "--qf", "%{SIZE}", pkg],
            capture_output=True,
            text=True,
            check=False,
        )
        val = result.stdout.strip()
        return int(val) if val.isdigit() else 0
    except Exception:
        return 0


def _group_by_version(pkgs: list[str]) -> dict[str, list[str]]:
    """Group package names by their kernel version string (newest first)."""
    groups: dict[str, list[str]] = {}
    for p in pkgs:
        # Robust extraction that handles all kernel-* component packages
        # kernel-7.0.9-205...  or  kernel-core-7.0.9-205... or kernel-modules-extra-...
        m = re.search(r'kernel(?:-[a-z-]+)?-(\d[^ ]+)', p)
        ver = m.group(1) if m else p
        groups.setdefault(ver, []).append(p)
    # Newest first
    return dict(sorted(groups.items(), reverse=True))


def clean_old_kernels(stats: SessionStats) -> None:
    """Interactive cleanup of old Fedora kernels using dnf's safe installonly support."""
    print_header("Clean Old Kernels")

    before = get_disk_snapshot()
    show_disk_snapshot(before, "Disk usage before kernel cleanup")

    running = _get_running_kernel()
    if running:
        print_info(f"Running kernel: {running}")
    else:
        print_warning("Could not determine the running kernel.")

    all_pkgs = _get_installonly_packages()
    if not all_pkgs:
        print_warning("Could not query installonly kernels via dnf. This may not be a Fedora system or dnf is unavailable.")
        return

    version_groups = _group_by_version(all_pkgs)
    print_info(f"Detected {len(version_groups)} distinct kernel version(s).")

    # Show user-friendly summary of current kernels
    print_info("Currently installed kernel versions (newest first):")
    for idx, (ver, pkg_list) in enumerate(version_groups.items(), 1):
        marker = "  (currently running)" if running and running in ver else ""
        print_info(f"  {idx}. {ver}{marker} — {len(pkg_list)} packages")

    if len(version_groups) <= 1:
        print_info("Only one kernel version is installed. Nothing can be safely removed.")
        return

    # Present keep choices (high-impact first, safe defaults)
    choices = [
        "Keep last 2 (recommended for most users)",
        "Keep last 3",
        "Keep last 4",
        "Custom number to keep...",
        "Show current state only (no changes)",
        "Cancel",
    ]

    selection = questionary.select(
        "How many of the newest kernels do you want to keep?",
        choices=choices,
    ).ask()

    if selection is None or selection == "Cancel":
        print_info("Cancelled. Returning to main menu.")
        return

    if "Show current" in selection:
        show_df_full()
        return

    keep = 2
    if "Custom" in selection:
        raw = questionary.text(
            "Enter the number of kernels to keep (minimum 1):",
            default="2",
        ).ask()
        try:
            keep = max(1, int((raw or "").strip()))
        except Exception:
            print_warning("Invalid number entered. Using default of 2.")
            keep = 2
    else:
        for token in selection.split():
            if token.isdigit():
                keep = int(token)
                break

    to_remove = _get_packages_to_remove(keep)
    if not to_remove:
        print_info(f"Keeping the last {keep} leaves no packages to remove.")
        return

    # Calculate sizes for preview
    sized_pkgs = []
    total_freed = 0
    for pkg in to_remove:
        sz = _get_package_size(pkg)
        sized_pkgs.append((pkg, sz))
        total_freed += sz

    # Rich preview table
    from rich.table import Table

    table = Table(
        title=f"Packages to be removed (keeping last {keep})",
        show_header=True,
        header_style="bold yellow",
    )
    table.add_column("Package")
    table.add_column("Size", justify="right")

    for pkg, sz in sized_pkgs:
        table.add_row(pkg, human_size(sz))

    console.print(table)
    console.print(f"\n[bold green]Estimated space that will be freed: {human_size(total_freed)}[/bold green]")

    # Strong safety messaging
    print_warning("This uses Fedora's official dnf mechanism for cleaning old kernels.")
    print_info("The currently running kernel is always protected and will not be removed.")
    print_info("A reboot after the operation is recommended (but not strictly required right away).")

    cmd = ["sudo", "dnf", "remove", "--oldinstallonly", f"--setopt=installonly_limit={keep}"]
    print_warning(f"Command that will be executed: {' '.join(cmd)}")
    print_info("You may be asked for your sudo password.")

    # Final confirmation
    if not questionary.confirm(
        "Proceed with removing the old kernels listed above?",
        default=False,
    ).ask():
        print_warning("Aborted by user. No kernels were removed.")
        return

    # Execute
    print_info("Running dnf to remove old kernels. This can take a minute...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout and result.stdout.strip():
            print_info(result.stdout.strip())
        if result.returncode == 0:
            print_success("Old kernels removed successfully.")
            if total_freed > 0:
                stats.add_purged(total_freed)
        else:
            print_error(f"dnf command failed with exit code {result.returncode}.")
            if result.stderr and result.stderr.strip():
                print_error(result.stderr.strip())
            return
    except FileNotFoundError:
        print_error("The 'dnf' command was not found. This feature requires a Fedora or RHEL-based system.")
        return
    except Exception as e:
        print_error(f"Unexpected error while running dnf: {e}")
        return

    # Post-cleanup visibility
    after = get_disk_snapshot()
    show_disk_snapshot(after, "Disk usage after kernel cleanup")
    show_df_full()
