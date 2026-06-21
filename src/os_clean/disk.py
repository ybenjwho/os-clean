"""Disk usage utilities and freed space tracking."""

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class DiskSnapshot:
    """Represents disk usage at a point in time."""
    timestamp: datetime
    total: str
    used: str
    avail: str
    use_pct: str
    mount: str = "/"

    def __str__(self) -> str:
        return f"{self.used} used / {self.total} ({self.use_pct}) on {self.mount}"


@dataclass
class SessionStats:
    """Tracks what was recovered during a session."""
    archived: int = 0          # bytes moved to archive
    purged: int = 0            # bytes actually deleted
    archive_paths: list[Path] = field(default_factory=list)

    @property
    def total_recovered(self) -> int:
        return self.archived + self.purged

    def add_archived(self, size_bytes: int, path: Optional[Path] = None) -> None:
        self.archived += size_bytes
        if path:
            self.archive_paths.append(path)

    def add_purged(self, size_bytes: int) -> None:
        self.purged += size_bytes

    def summary(self) -> str:
        """Short one-line summary (used by some flows)."""
        if self.total_recovered == 0:
            return "No space recovered this session."
        parts = []
        if self.purged:
            parts.append(f"Freed: {human_size(self.purged)}")
        if self.archived:
            parts.append(f"Archived: {human_size(self.archived)}")
        parts.append(f"Total: {human_size(self.total_recovered)}")
        return " | ".join(parts)


def human_size(num_bytes: int) -> str:
    """Convert bytes to human readable string."""
    if num_bytes == 0:
        return "0 B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def get_disk_snapshot(mount: str = "/") -> DiskSnapshot:
    """Get current disk usage via df -h for the given mount point."""
    try:
        result = subprocess.run(
            ["df", "-h", mount],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = result.stdout.strip().splitlines()
        if len(lines) >= 2:
            # Header: Filesystem Size Used Avail Use% Mounted on
            parts = lines[1].split()
            # df output can vary; try to extract sensibly
            # Typical: /dev/xxx  50G  30G  20G  60%  /
            if len(parts) >= 5:
                return DiskSnapshot(
                    timestamp=datetime.now(),
                    total=parts[1],
                    used=parts[2],
                    avail=parts[3],
                    use_pct=parts[4],
                    mount=parts[-1] if len(parts) > 5 else mount,
                )
    except Exception:
        pass

    # Fallback using shutil (less pretty)
    usage = shutil.disk_usage(mount)
    total = human_size(usage.total)
    used = human_size(usage.used)
    avail = human_size(usage.free)
    pct = f"{(usage.used / usage.total * 100):.0f}%"
    return DiskSnapshot(
        timestamp=datetime.now(),
        total=total,
        used=used,
        avail=avail,
        use_pct=pct,
        mount=mount,
    )


def run_df_full() -> str:
    """Return the raw pretty output of `df -h`."""
    try:
        result = subprocess.run(
            ["df", "-h"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception as e:
        return f"Unable to run df: {e}"


def get_path_size(path: Path) -> int:
    """Recursively compute size of a file or directory in bytes."""
    if not path.exists():
        return 0
    if path.is_file() or path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except Exception:
        pass
    return total


# --- Journal helpers ---

_JOURNAL_SIZE_RE = re.compile(
    r"take up\s+([\d.]+)\s*([KMGT]i?B?|[KMGT])", re.IGNORECASE
)


def _parse_journal_size_to_bytes(text: str) -> int:
    """Extract bytes from journalctl --disk-usage output like 'take up 248.3M'."""
    m = _JOURNAL_SIZE_RE.search(text)
    if not m:
        return 0
    val = float(m.group(1))
    unit = (m.group(2) or "").upper().replace("IB", "B").replace("I", "")
    mult_map = {"B": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}
    # Handle "MiB", "M", "MB" etc.
    key = unit[0] if unit else ""
    mult = mult_map.get(key, 1)
    return int(val * mult)


def get_journal_usage() -> str:
    """Return the human-readable output of `journalctl --disk-usage`."""
    try:
        result = subprocess.run(
            ["journalctl", "--disk-usage"],
            capture_output=True,
            text=True,
            check=False,
        )
        text = (result.stdout or result.stderr or "").strip()
        return text or "Unable to determine journal disk usage."
    except Exception as e:
        return f"Error querying journal usage: {e}"


def get_journal_size_bytes() -> int:
    """Return current journal size in bytes (parsed from journalctl)."""
    text = get_journal_usage()
    return _parse_journal_size_to_bytes(text)
