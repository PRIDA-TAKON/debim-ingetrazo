"""
debim-ingetrazo: Building-as-Code loader and live sync plugin for IngeTrazo.
"""

import sys
from pathlib import Path

# Ensure the plugin directory is present in sys.path so package-relative and
# absolute imports work cleanly when loaded by IngeTrazo's dynamic extension loader.
_parent_dir = str(Path(__file__).resolve().parent.parent)
if _parent_dir not in sys.path:
    sys.path.insert(0, _parent_dir)

from debim_ingetrazo.plugin import DebimPlugin, register_plugin, setup

__version__ = "0.1.0"

__all__ = ["DebimPlugin", "register_plugin", "setup", "__version__"]
