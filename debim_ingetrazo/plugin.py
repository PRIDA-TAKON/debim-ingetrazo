"""
IngeTrazo Plugin Entry Point for debim-ingetrazo.
"""

import math
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

    def __init__(self, app: Optional[Any] = None) -> None:
        super().__init__(name="debim_ingetrazo")
        self.app = app
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
        self.render_model_to_scene(model)
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
        win = None
        if self.app is not None:
            win = getattr(self.app, "_window", getattr(self.app, "window", None))

        if not self.console_dialog or not self.console_dialog.is_open:
            self.console_dialog = open_console_dialog(
                on_submit=self._on_live_debim_received,
                parent=win,
            )
        else:
            self.console_dialog.open()
        return self.console_dialog

    def _on_live_debim_received(
        self, content_str: str, manifest_dict: Dict[str, Any], building_model: Any
    ) -> None:
        """Callback invoked when new model geometry is received via Bridge, Watcher, or Console."""
        self.active_model = building_model
        self.render_model_to_scene(building_model)

    def _on_file_watcher_changed(
        self, file_path: Path, manifest_dict: Dict[str, Any], building_model: Any
    ) -> None:
        """Callback invoked when file watcher detects file modification."""
        self.active_model = building_model
        self.render_model_to_scene(building_model)

    def render_model_to_scene(self, model: Any) -> None:
        """
        Renders the BuildingModel entities directly into IngeTrazo's active scene mesh.
        """
        if self.app is None:
            return

        try:
            from PySide6.QtGui import QVector3D
        except ImportError:
            return

        scene = None
        viewport = None

        if hasattr(self.app, "scene") and callable(self.app.scene):
            scene = self.app.scene()
        elif hasattr(self.app, "_window") and hasattr(self.app._window, "viewport"):
            viewport = self.app._window.viewport
            scene = viewport.scene
        elif hasattr(self.app, "viewport"):
            viewport = self.app.viewport
            scene = getattr(viewport, "scene", None)

        if scene is None or not hasattr(scene, "mesh"):
            return

        mesh = scene.mesh
        face_count = 0

        # Traverse model storeys and build 3D mesh faces
        for st in getattr(model, "storeys", []):
            for child in getattr(st, "children", []):
                child_type = child.__class__.__name__

                if child_type == "Wall":
                    faces = self._build_wall_faces(child)
                elif child_type == "Slab":
                    faces = self._build_slab_faces(child)
                elif child_type == "Column":
                    faces = self._build_column_faces(child)
                else:
                    faces = []

                for loop in faces:
                    q_pts = [QVector3D(p[0], p[1], p[2]) for p in loop]
                    try:
                        mesh.add_face(q_pts)
                        face_count += 1
                    except Exception:
                        pass

        # Bump scene version and repaint viewport
        if hasattr(scene, "bump_view"):
            scene.bump_view()
        elif hasattr(scene, "version"):
            scene.version += 1

        if viewport is not None and hasattr(viewport, "update"):
            viewport.update()
        elif hasattr(self.app, "_window") and hasattr(self.app._window, "viewport"):
            self.app._window.viewport.update()

        # Update status message if available
        status_msg = f"debim: Loaded {getattr(model, 'name', 'model')} ({face_count} faces)"
        if hasattr(self.app, "flash_status"):
            self.app.flash_status(status_msg)
        elif viewport is not None and hasattr(viewport, "flash_status"):
            viewport.flash_status(status_msg)
        elif hasattr(self.app, "_window") and hasattr(self.app._window, "statusBar"):
            sb = self.app._window.statusBar()
            if sb:
                sb.showMessage(status_msg, 4000)

    @staticmethod
    def _build_wall_faces(wall: Any) -> List[List[tuple]]:
        start, end = wall.start, wall.end
        thickness, height, elevation = wall.thickness, wall.height, wall.elevation
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        L = math.hypot(dx, dy)
        if L == 0:
            return []
        nx = -dy / L * (thickness / 2.0)
        ny = dx / L * (thickness / 2.0)

        b0 = (start[0] + nx, start[1] + ny, elevation)
        b1 = (end[0] + nx, end[1] + ny, elevation)
        b2 = (end[0] - nx, end[1] - ny, elevation)
        b3 = (start[0] - nx, start[1] - ny, elevation)

        t0 = (start[0] + nx, start[1] + ny, elevation + height)
        t1 = (end[0] + nx, end[1] + ny, elevation + height)
        t2 = (end[0] - nx, end[1] - ny, elevation + height)
        t3 = (start[0] - nx, start[1] - ny, elevation + height)

        return [
            [b0, b3, b2, b1],  # bottom
            [t0, t1, t2, t3],  # top
            [b0, b1, t1, t0],  # side 1
            [b1, b2, t2, t1],  # end cap
            [b2, b3, t3, t2],  # side 2
            [b3, b0, t0, t3],  # start cap
        ]

    @staticmethod
    def _build_slab_faces(slab: Any) -> List[List[tuple]]:
        boundary, thickness, elevation = slab.boundary, slab.thickness, slab.elevation
        n = len(boundary)
        if n < 3:
            return []
        b_pts = [(p[0], p[1], elevation) for p in boundary]
        t_pts = [(p[0], p[1], elevation + thickness) for p in boundary]

        faces = [
            list(reversed(b_pts)),  # bottom
            list(t_pts),            # top
        ]
        for i in range(n):
            nxt = (i + 1) % n
            faces.append([b_pts[i], b_pts[nxt], t_pts[nxt], t_pts[i]])
        return faces

    @staticmethod
    def _build_column_faces(col: Any) -> List[List[tuple]]:
        pos = col.position
        sec = col.section
        radius = getattr(col, "radius", None)
        height = col.height
        elevation = col.elevation

        x, y = pos
        if radius is not None:
            segments = 16
            b_pts = []
            t_pts = []
            for i in range(segments):
                angle = 2 * math.pi * i / segments
                px = x + radius * math.cos(angle)
                py = y + radius * math.sin(angle)
                b_pts.append((px, py, elevation))
                t_pts.append((px, py, elevation + height))
            faces = [list(reversed(b_pts)), list(t_pts)]
            for i in range(segments):
                nxt = (i + 1) % segments
                faces.append([b_pts[i], b_pts[nxt], t_pts[nxt], t_pts[i]])
            return faces
        else:
            hw, hd = sec[0] / 2.0, sec[1] / 2.0
            boundary = [
                (x - hw, y - hd),
                (x + hw, y - hd),
                (x + hw, y + hd),
                (x - hw, y + hd),
            ]
            b_pts = [(p[0], p[1], elevation) for p in boundary]
            t_pts = [(p[0], p[1], elevation + height) for p in boundary]
            faces = [list(reversed(b_pts)), list(t_pts)]
            for i in range(4):
                nxt = (i + 1) % 4
                faces.append([b_pts[i], b_pts[nxt], t_pts[nxt], t_pts[i]])
            return faces


def register_plugin(app: Optional[Any] = None) -> DebimPlugin:
    """
    Entry point function called by IngeTrazo's Python plugin loader.
    """
    plugin = DebimPlugin(app=app)
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
            win = getattr(app, "_window", getattr(app, "window", None))
            path, _ = QFileDialog.getOpenFileName(
                win,
                "Select .debim Manifest",
                "",
                "debim Files (*.debim *.yaml *.yml);;All Files (*.*)",
            )
            if path:
                plugin.import_manifest(path)
        except Exception as e:
            print(f"[debim] Error importing manifest: {e}")

    def on_live_sync() -> None:
        enabled = plugin.toggle_live_sync()
        status_text = f"debim Live Sync: {'ON' if enabled else 'OFF'}"
        if hasattr(app, "flash_status"):
            app.flash_status(status_text)
        elif hasattr(app, "_window") and hasattr(app._window, "viewport"):
            app._window.viewport.flash_status(status_text)

    def on_console() -> None:
        try:
            plugin.open_agentic_ai_console()
        except Exception as e:
            print(f"[debim] Error opening AI Console: {e}")

    # Register in IngeTrazo menu
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
