"""
IngeTrazo Plugin Entry Point for debim-ingetrazo.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    from ingetrazo.sdk import Tool  # type: ignore
except ImportError:
    class Tool:
        """Fallback base Tool class when IngeTrazo SDK is not present in test environment."""
        def __init__(self, name: str = "DebimPluginTool") -> None:
            self.name = name
            self.active = False

        def activate(self) -> None:
            self.active = True

        def deactivate(self) -> None:
            self.active = False


class DebimPlugin(Tool):
    """
    Plugin implementation for debim OpenBIM Building-as-Code loader and live sync.
    """

    def __init__(self) -> None:
        super().__init__(name="debim_ingetrazo")
        self.resources_dir = Path(__file__).resolve().parent / "resources"
        self.icon_svg = self.resources_dir / "icon.svg"
        self.icon_png = self.resources_dir / "icon.png"
        self.live_sync_enabled = False

    def get_menu_registration(self) -> Dict[str, Any]:
        """
        Returns the menu structure to register under Extensions > debim.
        """
        return {
            "menu_path": "Extensions > debim",
            "items": [
                {
                    "label": "Import .debim Manifest...",
                    "action": self.import_manifest,
                    "shortcut": "Ctrl+Shift+D",
                },
                {
                    "label": "Toggle Live Sync",
                    "action": self.toggle_live_sync,
                    "checkable": True,
                    "checked": self.live_sync_enabled,
                },
                {
                    "label": "Open Agentic AI Console",
                    "action": self.open_agentic_ai_console,
                    "shortcut": "Ctrl+Shift+A",
                },
            ],
        }

    def get_toolbar_registration(self) -> Dict[str, Any]:
        """
        Returns toolbar action configuration with SVG/PNG icon.
        """
        icon_path = self.icon_svg if self.icon_svg.exists() else self.icon_png
        return {
            "toolbar_name": "debim",
            "action": {
                "label": "debim Building-as-Code",
                "tooltip": "debim — Declarative OpenBIM Manifest Loader & Live Sync",
                "icon": str(icon_path),
                "action": self.import_manifest,
            },
        }

    def import_manifest(self) -> None:
        """
        Handler for 'Import .debim Manifest...'.
        """
        # Placeholder for manifest import handling
        pass

    def toggle_live_sync(self) -> bool:
        """
        Handler for 'Toggle Live Sync'.
        """
        self.live_sync_enabled = not self.live_sync_enabled
        return self.live_sync_enabled

    def open_agentic_ai_console(self) -> None:
        """
        Handler for 'Open Agentic AI Console'.
        """
        # Placeholder for Agentic AI Console opening
        pass


def register_plugin(app: Optional[Any] = None) -> DebimPlugin:
    """
    Entry point function called by IngeTrazo's Python plugin loader.
    """
    plugin = DebimPlugin()
    if app is not None and hasattr(app, "register_tool"):
        app.register_tool(plugin)
    return plugin
