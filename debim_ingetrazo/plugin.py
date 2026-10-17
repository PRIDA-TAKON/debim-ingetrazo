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

        # Render 2D/3D Grid line axes and text balloons
        grid_sys = getattr(model, "grid_system", None)
        if grid_sys is not None:
            grid_faces = self._build_grid_faces(grid_sys)
            for loop in grid_faces:
                q_pts = [QVector3D(p[0], p[1], p[2]) for p in loop]
                try:
                    mesh.add_face(q_pts)
                    face_count += 1
                except Exception:
                    pass

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
                elif child_type == "Beam":
                    faces = self._build_beam_faces(child)
                elif child_type == "Footing":
                    faces = self._build_footing_faces(child)
                elif child_type == "Roof":
                    faces = self._build_roof_faces(child)
                elif child_type == "Stair":
                    faces = self._build_stair_faces(child)
                elif child_type == "Space":
                    faces = self._build_space_faces(child)
                elif child_type == "Door":
                    faces = self._build_door_faces(child)
                elif child_type == "Window":
                    faces = self._build_window_faces(child)
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
    def _build_grid_faces(grid_sys: Any, z_elevation: float = 0.0) -> List[List[tuple]]:
        """
        Constructs 3D mesh quad faces for grid line axes and 12-sided polygon faces for balloon markers.
        """
        grid_lines = grid_sys.get_grid_lines(margin=1.5, elevation=z_elevation)
        faces: List[List[tuple]] = []
        line_w = 0.02  # half-width = 0.02m (total line width = 0.04m)
        balloon_r = 0.35  # balloon circle radius = 0.35m

        for gline in grid_lines:
            axis = gline.get("axis")
            st = gline.get("start")
            en = gline.get("end")

            if not st or not en:
                continue

            # Grid Line Ribbon
            if axis == "X":
                # Vertical line running along Y
                faces.append([
                    (st[0] - line_w, st[1], st[2]),
                    (st[0] + line_w, st[1], st[2]),
                    (en[0] + line_w, en[1], en[2]),
                    (en[0] - line_w, en[1], en[2]),
                ])
            else:
                # Horizontal line running along X
                faces.append([
                    (st[0], st[1] - line_w, st[2]),
                    (en[0], en[1] - line_w, en[2]),
                    (en[0], en[1] + line_w, en[2]),
                    (st[0], st[1] + line_w, st[2]),
                ])

            # Grid Balloon Circles (12-sided polygon face at start & end)
            for bx, by, bz in gline.get("balloons", []):
                poly_pts = []
                for i in range(12):
                    angle = 2.0 * math.pi * i / 12.0
                    px = bx + balloon_r * math.cos(angle)
                    py = by + balloon_r * math.sin(angle)
                    poly_pts.append((px, py, bz))
                faces.append(poly_pts)

        return faces

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

    @staticmethod
    def _build_beam_faces(beam: Any) -> List[List[tuple]]:
        start, end = beam.start, beam.end
        width, depth, elevation = beam.width, beam.depth, beam.elevation
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        L = math.hypot(dx, dy)
        if L == 0:
            return []
        nx = -dy / L * (width / 2.0)
        ny = dx / L * (width / 2.0)

        elev_ref = (
            getattr(beam, "properties", {}).get("elevation_ref", "bottom")
            if hasattr(beam, "properties") and beam.properties
            else "bottom"
        )
        if elev_ref == "top":
            z_bot = elevation - depth
            z_top = elevation
        else:
            z_bot = elevation
            z_top = elevation + depth

        b0 = (start[0] + nx, start[1] + ny, z_bot)
        b1 = (end[0] + nx, end[1] + ny, z_bot)
        b2 = (end[0] - nx, end[1] - ny, z_bot)
        b3 = (start[0] - nx, start[1] - ny, z_bot)

        t0 = (start[0] + nx, start[1] + ny, z_top)
        t1 = (end[0] + nx, end[1] + ny, z_top)
        t2 = (end[0] - nx, end[1] - ny, z_top)
        t3 = (start[0] - nx, start[1] - ny, z_top)

        return [
            [b0, b3, b2, b1],  # bottom
            [t0, t1, t2, t3],  # top
            [b0, b1, t1, t0],  # side 1
            [b1, b2, t2, t1],  # end cap
            [b2, b3, t3, t2],  # side 2
            [b3, b0, t0, t3],  # start cap
        ]

    @staticmethod
    def _build_footing_faces(footing: Any) -> List[List[tuple]]:
        x, y = footing.position
        hw, hd = footing.section[0] / 2.0, footing.section[1] / 2.0
        z_bot = footing.elevation
        z_top = z_bot + footing.thickness

        b0 = (x - hw, y - hd, z_bot)
        b1 = (x + hw, y - hd, z_bot)
        b2 = (x + hw, y + hd, z_bot)
        b3 = (x - hw, y + hd, z_bot)

        t0 = (x - hw, y - hd, z_top)
        t1 = (x + hw, y - hd, z_top)
        t2 = (x + hw, y + hd, z_top)
        t3 = (x - hw, y + hd, z_top)

        return [
            [b0, b3, b2, b1],  # bottom
            [t0, t1, t2, t3],  # top
            [b0, b1, t1, t0],  # side 1
            [b1, b2, t2, t1],  # side 2
            [b2, b3, t3, t2],  # side 3
            [b3, b0, t0, t3],  # side 4
        ]

    @staticmethod
    def _build_roof_faces(roof: Any) -> List[List[tuple]]:
        poly = getattr(roof, "eaves_boundary", None) or getattr(roof, "boundary", [])
        if not poly or len(poly) < 3:
            return []

        roof_type = getattr(roof, "roof_type", "gable").lower()
        pitch = getattr(roof, "pitch", 30.0)
        z_eaves = getattr(roof, "elevation", 0.0)
        thickness = getattr(roof, "thickness", 0.2)
        ridge_dir = getattr(roof, "ridge_direction", "X").upper()
        pitch_rad = math.radians(pitch)

        min_x = min(p[0] for p in poly)
        max_x = max(p[0] for p in poly)
        min_y = min(p[1] for p in poly)
        max_y = max(p[1] for p in poly)
        w_x = max_x - min_x
        w_y = max_y - min_y

        if roof_type == "flat":
            z_top = z_eaves + thickness
            b_pts = [(p[0], p[1], z_eaves) for p in poly]
            t_pts = [(p[0], p[1], z_top) for p in poly]
            faces = [list(reversed(b_pts)), list(t_pts)]
            n = len(poly)
            for i in range(n):
                nxt = (i + 1) % n
                faces.append([b_pts[i], b_pts[nxt], t_pts[nxt], t_pts[i]])
            return faces

        e1 = (min_x, min_y, z_eaves)
        e2 = (max_x, min_y, z_eaves)
        e3 = (max_x, max_y, z_eaves)
        e4 = (min_x, max_y, z_eaves)

        if roof_type == "gable":
            if ridge_dir == "X":
                y_mid = (min_y + max_y) / 2.0
                h_ridge = (w_y / 2.0) * math.tan(pitch_rad)
                z_ridge = z_eaves + h_ridge
                r1 = (min_x, y_mid, z_ridge)
                r2 = (max_x, y_mid, z_ridge)

                return [
                    [e1, e2, r2, r1],  # South slope
                    [e3, e4, r1, r2],  # North slope
                    [e1, r1, e4],      # West gable end
                    [e2, e3, r2],      # East gable end
                ]
            else:
                x_mid = (min_x + max_x) / 2.0
                h_ridge = (w_x / 2.0) * math.tan(pitch_rad)
                z_ridge = z_eaves + h_ridge
                r1 = (x_mid, min_y, z_ridge)
                r2 = (x_mid, max_y, z_ridge)

                return [
                    [e1, r1, r2, e4],  # West slope
                    [e2, e3, r2, r1],  # East slope
                    [e1, e2, r1],      # South gable end
                    [e4, r2, e3],      # North gable end
                ]

        elif roof_type == "hip":
            if w_x >= w_y:
                y_mid = (min_y + max_y) / 2.0
                h_ridge = (w_y / 2.0) * math.tan(pitch_rad)
                z_ridge = z_eaves + h_ridge
                r1 = (min_x + w_y / 2.0, y_mid, z_ridge)
                r2 = (max_x - w_y / 2.0, y_mid, z_ridge)

                return [
                    [e1, e2, r2, r1],  # South slope
                    [e2, e3, r2],      # East slope
                    [e3, e4, r1, r2],  # North slope
                    [e4, e1, r1],      # West slope
                ]
            else:
                x_mid = (min_x + max_x) / 2.0
                h_ridge = (w_x / 2.0) * math.tan(pitch_rad)
                z_ridge = z_eaves + h_ridge
                r1 = (x_mid, min_y + w_x / 2.0, z_ridge)
                r2 = (x_mid, max_y - w_x / 2.0, z_ridge)

                return [
                    [e1, e2, r1],      # South slope
                    [e2, e3, r2, r1],  # East slope
                    [e4, e3, r2],      # North slope
                    [e1, r1, r2, e4],  # West slope
                ]

        elif roof_type == "shed":
            if ridge_dir == "X":
                h_rise = w_y * math.tan(pitch_rad)
                s1 = (min_x, min_y, z_eaves)
                s2 = (max_x, min_y, z_eaves)
                s3 = (max_x, max_y, z_eaves + h_rise)
                s4 = (min_x, max_y, z_eaves + h_rise)

                return [
                    [s1, s2, s3, s4],                            # Sloping quad
                    [s1, s4, (min_x, max_y, z_eaves)],           # West triangle
                    [s2, (max_x, max_y, z_eaves), s3],           # East triangle
                    [(min_x, max_y, z_eaves), (max_x, max_y, z_eaves), s3, s4],  # North high wall
                ]
            else:
                h_rise = w_x * math.tan(pitch_rad)
                s1 = (min_x, min_y, z_eaves)
                s2 = (max_x, min_y, z_eaves + h_rise)
                s3 = (max_x, max_y, z_eaves + h_rise)
                s4 = (min_x, max_y, z_eaves)

                return [
                    [s1, s2, s3, s4],                            # Sloping quad
                    [s1, s2, (max_x, min_y, z_eaves)],           # South triangle
                    [s4, (max_x, max_y, z_eaves), s3],           # North triangle
                    [(max_x, min_y, z_eaves), (max_x, max_y, z_eaves), s3, s2],  # East high wall
                ]

        return []

    @staticmethod
    def _build_box_faces(
        cx: float, cy: float, w: float, d: float, z_min: float, z_max: float, angle_deg: float = 0.0
    ) -> List[List[tuple]]:
        rad = math.radians(angle_deg)
        ux, uy = math.cos(rad), math.sin(rad)
        vx, vy = -uy, ux

        hw, hd = w / 2.0, d / 2.0
        c0 = (cx - hw * ux - hd * vx, cy - hw * uy - hd * vy)
        c1 = (cx + hw * ux - hd * vx, cy + hw * uy - hd * vy)
        c2 = (cx + hw * ux + hd * vx, cy + hw * uy + hd * vy)
        c3 = (cx - hw * ux + hd * vx, cy - hw * uy + hd * vy)

        b0 = (c0[0], c0[1], z_min)
        b1 = (c1[0], c1[1], z_min)
        b2 = (c2[0], c2[1], z_min)
        b3 = (c3[0], c3[1], z_min)

        t0 = (c0[0], c0[1], z_max)
        t1 = (c1[0], c1[1], z_max)
        t2 = (c2[0], c2[1], z_max)
        t3 = (c3[0], c3[1], z_max)

        return [
            [b0, b3, b2, b1],  # bottom
            [t0, t1, t2, t3],  # top
            [b0, b1, t1, t0],  # side 1
            [b1, b2, t2, t1],  # side 2
            [b2, b3, t3, t2],  # side 3
            [b3, b0, t0, t3],  # side 4
        ]

    @staticmethod
    def _build_stair_faces(stair: Any) -> List[List[tuple]]:
        start, end = stair.start, stair.end
        width, height = stair.width, stair.height
        num_steps = getattr(stair, "num_steps", 16)
        riser_h = getattr(stair, "riser_height", height / max(1, num_steps))
        tread_d = getattr(stair, "tread_depth", 0.28)
        elevation = stair.elevation
        landing_d = getattr(stair, "landing_depth", 0.0)
        landing_t = getattr(stair, "landing_thickness", 0.15)

        dx = end[0] - start[0]
        dy = end[1] - start[1]
        run_len = math.hypot(dx, dy)
        if run_len == 0:
            ux, uy = 1.0, 0.0
        else:
            ux, uy = dx / run_len, dy / run_len

        angle_deg = math.degrees(math.atan2(uy, ux))
        faces: List[List[tuple]] = []

        for i in range(num_steps):
            dist_i = (i + 0.5) * tread_d
            cx = start[0] + dist_i * ux
            cy = start[1] + dist_i * uy
            z_bot = elevation + i * riser_h
            z_top = elevation + (i + 1) * riser_h
            step_faces = DebimPlugin._build_box_faces(
                cx, cy, tread_d, width, z_bot, z_top, angle_deg
            )
            faces.extend(step_faces)

        if landing_d > 0:
            dist_landing = num_steps * tread_d + landing_d / 2.0
            cx = start[0] + dist_landing * ux
            cy = start[1] + dist_landing * uy
            z_top = elevation + height
            z_bot = z_top - landing_t
            landing_faces = DebimPlugin._build_box_faces(
                cx, cy, landing_d, width, z_bot, z_top, angle_deg
            )
            faces.extend(landing_faces)

        return faces

    @staticmethod
    def _build_space_faces(space: Any) -> List[List[tuple]]:
        boundary, height, elevation = space.boundary, space.height, space.elevation
        n = len(boundary)
        if n < 3:
            return []
        b_pts = [(p[0], p[1], elevation) for p in boundary]
        t_pts = [(p[0], p[1], elevation + height) for p in boundary]

        faces = [
            list(reversed(b_pts)),  # floor
            list(t_pts),            # ceiling
        ]
        for i in range(n):
            nxt = (i + 1) % n
            faces.append([b_pts[i], b_pts[nxt], t_pts[nxt], t_pts[i]])
        return faces

    @staticmethod
    def _build_door_faces(door: Any) -> List[List[tuple]]:
        x, y = door.position
        w, h, depth = door.width, door.height, door.depth
        frame_w = door.frame_width
        panel_t = door.panel_thickness
        z_min = door.elevation + door.sill_height
        z_max = z_min + h
        angle_deg = door.direction

        rad = math.radians(angle_deg)
        ux, uy = math.cos(rad), math.sin(rad)

        faces: List[List[tuple]] = []

        # Top frame member
        z_top_frame_min = z_max - frame_w
        top_frame = DebimPlugin._build_box_faces(x, y, w, depth, z_top_frame_min, z_max, angle_deg)
        faces.extend(top_frame)

        # Left jamb frame
        hw_inner = (w / 2.0) - (frame_w / 2.0)
        left_cx = x - hw_inner * ux
        left_cy = y - hw_inner * uy
        left_jamb = DebimPlugin._build_box_faces(left_cx, left_cy, frame_w, depth, z_min, z_top_frame_min, angle_deg)
        faces.extend(left_jamb)

        # Right jamb frame
        right_cx = x + hw_inner * ux
        right_cy = y + hw_inner * uy
        right_jamb = DebimPlugin._build_box_faces(right_cx, right_cy, frame_w, depth, z_min, z_top_frame_min, angle_deg)
        faces.extend(right_jamb)

        # Leaf door panel
        w_panel = max(0.01, w - 2 * frame_w)
        panel = DebimPlugin._build_box_faces(x, y, w_panel, panel_t, z_min, z_top_frame_min, angle_deg)
        faces.extend(panel)

        return faces

    @staticmethod
    def _build_window_faces(window: Any) -> List[List[tuple]]:
        x, y = window.position
        w, h, depth = window.width, window.height, window.depth
        frame_w = window.frame_width
        glass_t = window.glass_thickness
        z_min = window.elevation + window.sill_height
        z_max = z_min + h
        angle_deg = window.direction

        rad = math.radians(angle_deg)
        ux, uy = math.cos(rad), math.sin(rad)

        faces: List[List[tuple]] = []

        # Top frame
        top_frame = DebimPlugin._build_box_faces(x, y, w, depth, z_max - frame_w, z_max, angle_deg)
        faces.extend(top_frame)

        # Bottom frame
        bot_frame = DebimPlugin._build_box_faces(x, y, w, depth, z_min, z_min + frame_w, angle_deg)
        faces.extend(bot_frame)

        # Left jamb
        hw_inner = (w / 2.0) - (frame_w / 2.0)
        left_cx = x - hw_inner * ux
        left_cy = y - hw_inner * uy
        left_jamb = DebimPlugin._build_box_faces(left_cx, left_cy, frame_w, depth, z_min + frame_w, z_max - frame_w, angle_deg)
        faces.extend(left_jamb)

        # Right jamb
        right_cx = x + hw_inner * ux
        right_cy = y + hw_inner * uy
        right_jamb = DebimPlugin._build_box_faces(right_cx, right_cy, frame_w, depth, z_min + frame_w, z_max - frame_w, angle_deg)
        faces.extend(right_jamb)

        # Glazed glass panel
        w_glass = max(0.01, w - 2 * frame_w)
        glass_panel = DebimPlugin._build_box_faces(x, y, w_glass, glass_t, z_min + frame_w, z_max - frame_w, angle_deg)
        faces.extend(glass_panel)

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
