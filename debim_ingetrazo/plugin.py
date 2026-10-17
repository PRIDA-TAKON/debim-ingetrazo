"""
IngeTrazo Plugin Entry Point for debim-ingetrazo.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional, Union

from debim_ingetrazo.agent_bridge import AgentBridge
from debim_ingetrazo.console import AIConsoleDialog, open_console_dialog
from debim_ingetrazo.watcher import DebimWatcher

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
        self.active_model: Optional[Any] = None
        self.active_file_path: Optional[Path] = None

        # Agent Bridge and Watcher components
        self.agent_bridge = AgentBridge(on_debim_received=self._on_live_debim_received)
        self.file_watcher = DebimWatcher(on_file_changed=self._on_file_watcher_changed)
        self.console_dialog: Optional[AIConsoleDialog] = None

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

    def import_manifest(self, file_path_or_str: Optional[Union[str, Path]] = None) -> Optional[Any]:
        """
        Handler for 'Import .debim Manifest...'.
        Parses the manifest and builds 3D geometry objects.
        """
        from debim_ingetrazo.parser import parse_debim, parse_debim_str
        from debim_ingetrazo.builder import build_geometry

        if file_path_or_str is None:
            return None

        if isinstance(file_path_or_str, (str, Path)) and Path(file_path_or_str).exists():
            path = Path(file_path_or_str)
            manifest = parse_debim(path)
            self.active_file_path = path
            if self.file_watcher:
                self.file_watcher.set_target_file(path)
        elif isinstance(file_path_or_str, str):
            manifest = parse_debim_str(file_path_or_str)
        else:
            return None

        model = build_geometry(manifest)
        self.active_model = model
        return model

    def toggle_live_sync(self) -> bool:
        """
        Handler for 'Toggle Live Sync'.
        Starts or stops background Agent Bridge and File Watcher.
        """
        self.live_sync_enabled = not self.live_sync_enabled

        if self.live_sync_enabled:
            self.agent_bridge.start()
            if self.active_file_path and self.active_file_path.exists():
                self.file_watcher.set_target_file(self.active_file_path)
                self.file_watcher.start()
        else:
            self.agent_bridge.stop()
            self.file_watcher.stop()

        return self.live_sync_enabled

    def open_agentic_ai_console(self) -> AIConsoleDialog:
        """
        Handler for 'Open Agentic AI Console'.
        Launches interactive AI Console dialog.
        """
        if not self.console_dialog or not self.console_dialog.is_open:
            self.console_dialog = open_console_dialog(
                on_submit=self._on_live_debim_received
            )
        else:
            self.console_dialog.open()
        return self.console_dialog

    def _on_live_debim_received(
        self, content_str: str, manifest_dict: Dict[str, Any], building_model: Any
    ) -> None:
        """Callback invoked when new model geometry is received via Bridge, Watcher, or Console."""
        self.active_model = building_model

    def _on_file_watcher_changed(
        self, file_path: Path, manifest_dict: Dict[str, Any], building_model: Any
    ) -> None:
        """Callback invoked when file watcher detects file modification."""
        self.active_model = building_model


def register_plugin(app: Optional[Any] = None) -> DebimPlugin:
    """
    Entry point function called by IngeTrazo's Python plugin loader.
    """
    plugin = DebimPlugin()
    if app is not None and hasattr(app, "register_tool"):
        app.register_tool(plugin)
    return plugin


def setup(app: Any) -> None:
    """
    Official setup(app) entry point called by IngeTrazo's extension loader.
    """
    plugin = register_plugin(app)

    def on_import() -> None:
        try:
            from PySide6.QtWidgets import QFileDialog
            win = getattr(app, "window", None)
            path, _ = QFileDialog.getOpenFileName(
                win,
                "Select .debim Manifest",
                "",
                "debim Files (*.debim *.yaml *.yml);;All Files (*.*)",
            )
            if path:
                plugin.import_manifest(path)
                if hasattr(app, "viewport") and hasattr(app.viewport, "update"):
                    app.viewport.update()
        except Exception as e:
            print(f"[debim] Error importing manifest: {e}")

    def on_live_sync() -> None:
        enabled = plugin.toggle_live_sync()
        if hasattr(app, "viewport") and hasattr(app.viewport, "flash_status"):
            app.viewport.flash_status(f"debim Live Sync: {'ON' if enabled else 'OFF'}")

    def on_console() -> None:
        plugin.open_agentic_ai_console()

    # Try registering via app.add_menu / add_menu_action
    if hasattr(app, "add_menu"):
        sub = app.add_menu("debim")
        if sub is not None:
            sub.addAction("Import .debim Manifest...", on_import)
            sub.addAction("Toggle Live Sync", on_live_sync)
            sub.addAction("Open Agentic AI Console", on_console)
    elif hasattr(app, "add_menu_action"):
        app.add_menu_action("debim: Import Manifest...", on_import, "Ctrl+Shift+D", "Import .debim OpenBIM manifest")
        app.add_menu_action("debim: Toggle Live Sync", on_live_sync, "", "Toggle live hot-reload sync")
        app.add_menu_action("debim: AI Console", on_console, "Ctrl+Shift+A", "Open debim AI Console")

