"""Cleanup modules for os-clean.\n\nModules are imported lazily inside cli.py and the specific module files\nso that a partially complete checkout still imports.\n"""

# Intentionally do not auto-import submodules here.
# Each module (downloads, kernels, ...) is imported explicitly where needed.
