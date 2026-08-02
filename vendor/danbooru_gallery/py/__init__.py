"""Minimal private package namespace for Xiawan's gallery node vendor."""

from pathlib import Path
from types import SimpleNamespace

__version__ = "1.0.0"

# Preserve the original compatibility shim without installing unrelated hooks.
path = SimpleNamespace(local=Path)
__all__ = ["path"]
