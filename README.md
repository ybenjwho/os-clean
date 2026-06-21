# os-clean

Safe, iterative, interactive terminal tool to explore and clean your Linux system (Fedora first).

## Philosophy
- **Safety first**: Never delete without confirmation. Prefer Archive → Review → Delete.
- **Iterative**: Run multiple cleanup rounds in one session.
- **Visible**: Always show disk usage (`df -h`) before and after actions.
- **Beautiful UX**: Powered by `rich` + `questionary`.
- **Modular**: Easy to add new cleanup modules (Downloads, Kernels, Journals, Flatpak, Docker...).

## Version 1 (MVP)
- Welcome + current disk usage (always shown before/after actions)
- Main menu (prioritized by impact): Clean Journal Logs → Clean Old Kernels → Clean Downloads → Show System Overview → Exit
- Downloads: largest items via `dust`, multi-select + Archive or Purge (with clear space impact preview)
- Journal Logs: presets + custom vacuum using `journalctl --vacuum-*` (with sudo handling)
- After every major action: updated disk usage + space freed summary
- End-of-session summary with clear separation of freed vs archived space
- Built-in Help / About for onboarding and reference

## Installation

### Recommended (one-command elegant setup)

```bash
cd ~/os-clean
bash install.sh
```

This sets up the venv + editable install and prints the recommended aliases.

### Manual elegant install

```bash
cd ~/os-clean
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then add aliases (see below).

### Global user install

```bash
pip install --user -e .
# Make sure ~/.local/bin is in your PATH
```

### Packaging notes

This project uses modern Python packaging (`pyproject.toml`). After `pip install -e .`, the `os-clean` entry point is automatically created. 

The package exposes:
- Command: `os-clean`
- Module: `python -m os_clean`
- Supports: `os-clean --help` and `os-clean --version`

### Easiest way to run (elegant)

After installing with pip, the `os-clean` command is available:

```bash
# Inside your venv
os-clean

# Or globally (if using --user)
os-clean
```

#### Recommended: Add convenient aliases

Add this to your `~/.bashrc` or `~/.zshrc`:

```bash
# os-clean aliases (highly recommended)
alias oc='os-clean'
alias clean='os-clean'
alias disk-clean='os-clean'
```

Then reload:

```bash
source ~/.zshrc   # or ~/.bashrc
```

You can now type `oc` or `clean` for a very elegant experience.

You can also source the project's helper:

```bash
source ~/os-clean/scripts/aliases.sh
```

#### Direct module run (fallback)

```bash
python -m os_clean.cli
```

#### Even more elegant: using pipx (isolated install)

```bash
pipx install -e .
os-clean
```

## Usage

```bash
os-clean
```

The tool **always** shows disk usage (`df -h`) before and after every major action.  
A "Help / About os-clean" option in the main menu explains Archive vs Purge and the safety model.

## Safety Notes
- Archiving moves items to `~/Archive/Old_Downloads_2026/<timestamp>/` (or per-module equivalents)
- Nothing is purged without explicit multi-step confirmation (including a "PURGE" typed confirmation for deletes)
- You can always skip
- Archive first, review later, purge only when you're sure

## Implemented & Future Modules
- Journal Logs (implemented)
- Old Kernels via dnf (implemented)
- Downloads (implemented)
- Future ideas: Flatpak, Docker/Podman, thumbnail/cache cleanup, package cache, etc.

## Contributing to your own tool
This is a personal tool. Extend `src/os_clean/modules/` for new areas.
