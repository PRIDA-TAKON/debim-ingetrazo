"""
debim-ingetrazo: Building-as-Code loader and live sync plugin for IngeTrazo.
"""

from debim_ingetrazo.plugin import DebimPlugin, register_plugin, setup

__version__ = "0.1.0"

__all__ = ["DebimPlugin", "register_plugin", "setup", "__version__"]
