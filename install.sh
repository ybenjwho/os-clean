#!/usr/bin/env bash
#
# Elegant one-command setup for os-clean
# Usage:
#   bash install.sh
#

set -e

echo "🚀 Installing os-clean with elegant UX..."

# 1. Create venv if not exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate

# 2. Install in editable mode
echo "Installing package (editable)..."
pip install -e . --quiet

# 3. Suggest aliases
echo ""
echo "✅ Installation complete!"
echo ""
echo "To get the most elegant experience, add an alias:"
echo ""
echo '    echo '\''alias oc="os-clean"'\'' >> ~/.zshrc   # or ~/.bashrc'
echo '    echo '\''alias clean="os-clean"'\'' >> ~/.zshrc'
echo ""
echo "Then reload your shell:"
echo "    source ~/.zshrc"
echo ""
echo "Now you can run:"
echo "    oc"
echo "    clean"
echo "    os-clean --version"
echo ""
echo "Tip: Source the included aliases:"
echo "    source $(pwd)/scripts/aliases.sh"
echo ""
echo "Happy cleaning! 🧹"