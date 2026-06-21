"""Main CLI entry point and interactive loop for os-clean."""

import argparse
import sys

import questionary

from . import __version__
from .disk import SessionStats, get_disk_snapshot
from .modules.downloads import clean_downloads
from .modules.journals import clean_journal_logs
from .modules.kernels import clean_old_kernels
from .ui import (
    print_header,
    print_info,
    print_welcome,
    show_disk_snapshot,
    show_df_full,
    show_help,
    show_session_summary,
)


def main() -> None:
    """Run the interactive os-clean tool.

    Supports elegant command-line usage:
        os-clean            # interactive menu
        os-clean --help
        os-clean --version
    """
    parser = argparse.ArgumentParser(
        prog="os-clean",
        description="Safe, interactive CLI tool to explore and clean your Linux system",
        epilog="Run without arguments for the interactive menu.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    # Parse known args so we don't break if future flags are added.
    # If --help or --version are used, argparse will exit here automatically.
    parser.parse_args()

    # No special flags — launch the beautiful interactive experience
    stats = SessionStats()
    print_welcome()

    try:
        while True:
            # Always show disk usage at the top of every loop
            snap = get_disk_snapshot("/")
            show_disk_snapshot(snap, "Current Disk Usage")

            choice = questionary.select(
                "Main Menu — What would you like to do?",
                choices=[
                    "Clean Journal Logs",   # Often large, low-risk wins (systemd journals)
                    "Clean Old Kernels",
                    "Clean Downloads",
                    "Show System Overview",
                    "Help / About os-clean",
                    "Exit",
                ],
            ).ask()

            if choice is None or choice == "Exit":
                break

            if choice == "Clean Downloads":
                clean_downloads(stats)
            elif choice == "Clean Journal Logs":
                clean_journal_logs(stats)
            elif choice == "Clean Old Kernels":
                clean_old_kernels(stats)
            elif choice == "Show System Overview":
                print_header("System Overview")
                show_df_full()
            elif choice == "Help / About os-clean":
                show_help()
            else:
                # Placeholder for future high-impact modules
                print_info(f"'{choice}' is not implemented yet.")
                print_info("It will be added in a future iteration.")
                # Still show disk after "doing nothing" so user sees continuity
                after = get_disk_snapshot("/")
                show_disk_snapshot(after, "Disk usage (no changes)")

            # Small breathing room / visual separation before next menu
            print()

    except KeyboardInterrupt:
        print_info("\nInterrupted by user (Ctrl+C).")
    finally:
        # Always give a nice closing summary
        show_session_summary(stats)


if __name__ == "__main__":
    main()