"""Journal logs cleanup module for os-clean.\n\nUses systemd's journalctl to safely reduce journal size.\nAlways shows impact on journal usage + overall disk usage.\nRequires sudo for vacuum operations (will prompt when necessary).\n"""

import subprocess

import questionary

from ..disk import (
    SessionStats,
    get_disk_snapshot,
    get_journal_size_bytes,
    get_journal_usage,
    human_size,
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


def _build_vacuum_arg(choice: str, custom_val: str | None = None) -> str | None:
    """Map user choice to the correct journalctl vacuum argument."""
    if "1 week" in choice:
        return "--vacuum-time=1week"
    elif "2 weeks" in choice:
        return "--vacuum-time=2weeks"
    elif "1 month" in choice:
        return "--vacuum-time=1month"
    elif "100 MiB" in choice:
        return "--vacuum-size=100M"
    elif "250 MiB" in choice:
        return "--vacuum-size=250M"
    elif "500 MiB" in choice:
        return "--vacuum-size=500M"
    elif custom_val:
        val = custom_val.strip()
        if not val:
            return None
        lowered = val.lower()
        # Heuristic: if it contains time units, use time; else size
        time_units = ("week", "month", "day", "hour", "year", "w", "d", "h", "m", "s")
        if any(u in lowered for u in time_units) or any(c.isalpha() and c not in "bkmgt" for c in lowered):
            return f"--vacuum-time={val}"
        else:
            return f"--vacuum-size={val}"
    return None


def clean_journal_logs(stats: SessionStats) -> None:
    """Interactive systemd journal cleanup.\n\n    Shows current journal usage, offers safe presets + custom option,
    runs with sudo (prompts for password if needed), and reports impact.
    """
    print_header("Clean Journal Logs")

    before = get_disk_snapshot()
    show_disk_snapshot(before, "Disk usage before journal cleanup")

    # Current journal state (no privileges needed)
    journal_before_text = get_journal_usage()
    journal_bytes_before = get_journal_size_bytes()

    print_info(f"Current journal usage: {journal_before_text}")
    if journal_bytes_before > 0:
        print_info(f"Parsed size: {human_size(journal_bytes_before)}")

    # Menu of safe, commonly useful actions
    choices = [
        "Vacuum logs older than 1 week",
        "Vacuum logs older than 2 weeks",
        "Vacuum logs older than 1 month",
        "Vacuum down to 100 MiB",
        "Vacuum down to 250 MiB",
        "Vacuum down to 500 MiB",
        "Custom value (time or size)...",
        "Show current journal usage only (no changes)",
        "Cancel",
    ]

    selection = questionary.select(
        "Select a journal cleanup action:",
        choices=choices,
    ).ask()

    if selection is None or selection == "Cancel":
        print_info("Cancelled. Returning to main menu.")
        return

    if "Show current" in selection:
        show_df_full()
        return

    custom_val = None
    if "Custom value" in selection:
        custom_val = questionary.text(
            "Enter vacuum argument (examples: 2weeks, 300M, 1month):",
            default="2weeks",
        ).ask()
        if not custom_val:
            print_info("No value provided. Cancelled.")
            return

    vacuum_arg = _build_vacuum_arg(selection, custom_val)
    if not vacuum_arg:
        print_warning("Could not determine vacuum command. Cancelled.")
        return

    # Build the command we will actually run
    cmd = ["sudo", "journalctl", vacuum_arg]

    print_warning(f"About to run: {' '.join(cmd)}")
    print_info("sudo may ask for your password in the terminal.")
    print_info("This operation is generally very safe (systemd journal only).")

    # Final confirmation
    if not questionary.confirm(
        "Execute the journal vacuum command above?", default=False
    ).ask():
        print_warning("Aborted by user.")
        return

    # Run it (try without sudo first in case user has journal permissions)
    print_info("Running journal vacuum. This may take a moment...")
    attempts = [cmd, ["sudo"] + cmd]
    success = False
    try:
        for attempt in attempts:
            result = subprocess.run(
                attempt,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                if result.stdout.strip():
                    print_info(result.stdout.strip())
                print_success("Journal vacuum completed successfully.")
                success = True
                break
            last_result = result

        if not success:
            print_error(f"journalctl exited with code {last_result.returncode}")
            if last_result.stderr.strip():
                print_error(last_result.stderr.strip())
            if "permission" in (last_result.stderr or "").lower():
                print_warning("You may need sudo privileges or membership in the 'systemd-journal' group.")
            return
    except FileNotFoundError:
        print_error("journalctl command not found. This tool requires a systemd-based system.")
        return
    except Exception as e:
        print_error(f"Unexpected error running journalctl: {e}")
        return

    # Measure impact
    after = get_disk_snapshot()
    journal_after_text = get_journal_usage()
    journal_bytes_after = get_journal_size_bytes()

    freed_journal = max(0, journal_bytes_before - journal_bytes_after)
    if freed_journal > 0:
        stats.add_purged(freed_journal)
        print_success(f"Journal space freed: {human_size(freed_journal)}")
    else:
        print_info("Journal size change was negligible or could not be measured precisely.")

    print_info(f"Journal usage now: {journal_after_text}")

    show_disk_snapshot(after, "Disk usage after journal cleanup")
    show_df_full()
