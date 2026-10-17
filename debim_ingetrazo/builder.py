"""
3D Entity Geometry Builder for debim-ingetrazo.
Converts parsed .debim manifest structures into native IngeTrazo 3D geometry objects.
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from debim_ingetrazo.parser import extract_elements


class GridSystem:
    """
    Parametric grid coordinate resolver for debim CLI schema.
    Resolves grid intersection labels and arithmetic offset expressions (e.g. GX_1 + 0.10, GY_A - 0.10).
    """

    def __init__(self, grids_data: Optional[Dict[str, Any]] = None):
        grids_data = grids_data or {}
        raw_x = grids_data.get("axes_x") or grids_data.get("x") or {}
        raw_y = grids_data.get("axes_y") or grids_data.get("y") or {}

        self.axes_x: Dict[str, float] = {}
        self.axes_y: Dict[str, float] = {}

        if isinstance(raw_x, dict):
            for k, v in raw_x.items():
                try:
                    self.axes_x[str(k)] = float(v)
                except (ValueError, TypeError):
                    pass
        elif isinstance(raw_x, list):
            for item in raw_x:
                if isinstance(item, dict) and "id" in item and "position" in item:
                    self.axes_x[str(item["id"])] = float(item["position"])

        if isinstance(raw_y, dict):
            for k, v in raw_y.items():
                try:
                    self.axes_y[str(k)] = float(v)
                except (ValueError, TypeError):
                    pass
        elif isinstance(raw_y, list):
            for item in raw_y:
                if isinstance(item, dict) and "id" in item and "position" in item:
                    self.axes_y[str(item["id"])] = float(item["position"])

    def _lookup_x(self, key: str) -> Optional[float]:
        if key in self.axes_x:
            return self.axes_x[key]
        if key.isdigit():
            idx = int(key) - 1
            x_vals = list(self.axes_x.values())
            if 0 <= idx < len(x_vals):
                return x_vals[idx]
        return None

    def _lookup_y(self, key: str) -> Optional[float]:
        if key in self.axes_y:
            return self.axes_y[key]
        if key.isdigit():
            idx = int(key) - 1
            y_vals = list(self.axes_y.values())
            if 0 <= idx < len(y_vals):
                return y_vals[idx]
        return None

    def eval_coord(self, val: Any, is_y: bool = False) -> float:
        """
        Evaluates a coordinate value, grid label reference, or arithmetic expression into float.
        """
        if isinstance(val, (int, float)):
            return float(val)

        if not isinstance(val, str):
            return 0.0

        s = val.strip()
        if not s:
            return 0.0

        if not is_y:
            lx = self._lookup_x(s)
            if lx is not None:
                return lx
        else:
            ly = self._lookup_y(s)
            if ly is not None:
                return ly

        if s.startswith("GX_"):
            lx = self._lookup_x(s[3:])
            if lx is not None:
                return lx
        if s.startswith("GY_"):
            ly = self._lookup_y(s[3:])
            if ly is not None:
                return ly

        expr = s
        tokens = re.findall(r'[A-Za-z_][A-Za-z0-9_]*|\d+[A-Za-z_][A-Za-z0-9_]*|\b[A-Za-z0-9_]+\b', s)
        tokens.sort(key=len, reverse=True)

        for tok in tokens:
            if tok.startswith("GX_"):
                lx = self._lookup_x(tok[3:])
                if lx is not None:
                    expr = re.sub(r'\b' + re.escape(tok) + r'\b', str(lx), expr)
            elif tok.startswith("GY_"):
                ly = self._lookup_y(tok[3:])
                if ly is not None:
                    expr = re.sub(r'\b' + re.escape(tok) + r'\b', str(ly), expr)
            elif not is_y:
                lx = self._lookup_x(tok)
                if lx is not None:
                    expr = re.sub(r'\b' + re.escape(tok) + r'\b', str(lx), expr)
            else:
                ly = self._lookup_y(tok)
                if ly is not None:
                    expr = re.sub(r'\b' + re.escape(tok) + r'\b', str(ly), expr)

        try:
            if re.match(r'^[0-9\.\+\-\*\/\(\)\s]+$', expr):
                return float(eval(expr, {"__builtins__": None}, {}))
        except Exception:
            pass

        try:
            return float(s)
        except ValueError:
            return 0.0

    def resolve_point(self, point_spec: Any) -> Tuple[float, float]:
        """
        Resolves a 2D point from grid intersection spec, coordinate tuple, or dict.
        """
        if isinstance(point_spec, dict):
            if "grid" in point_spec:
                return self.resolve_point(point_spec["grid"])
            x_val = point_spec.get("x", 0.0)
            y_val = point_spec.get("y", 0.0)
            return (self.eval_coord(x_val, is_y=False), self.eval_coord(y_val, is_y=True))

        if isinstance(point_spec, (list, tuple)) and len(point_spec) >= 2:
            x_res = self.eval_coord(point_spec[0], is_y=False)
            y_res = self.eval_coord(point_spec[1], is_y=True)
            return (x_res, y_res)

        if isinstance(point_spec, str):
            s = point_spec.strip()
            if "-" in s:
                parts = s.split("-", 1)
                return (self.eval_coord(parts[0], is_y=False), self.eval_coord(parts[1], is_y=True))
            elif "," in s:
                parts = s.split(",", 1)
                return (self.eval_coord(parts[0], is_y=False), self.eval_coord(parts[1], is_y=True))

        return (0.0, 0.0)

    def resolve_line(self, from_spec: Any, to_spec: Any) -> Tuple[Tuple[float, float], Tuple[float, float]]:
        """Resolves start and end points of a linear element."""
        p_start = self.resolve_point(from_spec)
        p_end = self.resolve_point(to_spec)
        return (p_start, p_end)

    def get_grid_lines(
        self, margin: float = 1.5, elevation: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Generates grid line 3D line coordinates and balloon positions for X and Y grid axes.
        """
        if not self.axes_x and not self.axes_y:
            return []

        x_coords = list(self.axes_x.values()) or [0.0]
        y_coords = list(self.axes_y.values()) or [0.0]

        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)

        if min_x == max_x:
            min_x, max_x = min_x - 5.0, max_x + 5.0
        if min_y == max_y:
            min_y, max_y = min_y - 5.0, max_y + 5.0

        grid_lines = []

        for label, x_val in self.axes_x.items():
            start_pt = (x_val, min_y - margin, elevation)
            end_pt = (x_val, max_y + margin, elevation)
            grid_lines.append({
                "axis": "X",
                "label": str(label),
                "position": x_val,
                "start": start_pt,
                "end": end_pt,
                "balloons": [start_pt, end_pt],
            })

        for label, y_val in self.axes_y.items():
            start_pt = (min_x - margin, y_val, elevation)
            end_pt = (max_x + margin, y_val, elevation)
            grid_lines.append({
                "axis": "Y",
                "label": str(label),
                "position": y_val,
                "start": start_pt,
                "end": end_pt,
                "balloons": [start_pt, end_pt],
            })

        return grid_lines

    def to_dict(self) -> Dict[str, Any]:
        return {
            "axes_x": self.axes_x,
            "axes_y": self.axes_y,
            "grid_lines": self.get_grid_lines(),
        }


class GeometryObject:
    """Base class for all native IngeTrazo geometry objects."""

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ):
        self.id = id_str
        self.name = name or id_str
        self.tag = tag
        self.properties = properties or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "tag": self.tag,
            "type": self.__class__.__name__,
            "properties": self.properties,
        }


class Group(GeometryObject):
    """Hierarchical Group representing project, building, or storey containers."""

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "A-GROUP",
        elevation: float = 0.0,
        height: float = 0.0,
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag, properties=properties)
        self.elevation = elevation
        self.height = height
        self.children: List[GeometryObject] = []

    def add_child(self, child: GeometryObject) -> None:
        self.children.append(child)

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res["elevation"] = self.elevation
        res["height"] = self.height
        res["children"] = [child.to_dict() for child in self.children]
        return res


class Slab(GeometryObject):
    """Solid Face Extrusion representing floor or roof slabs (S-SLAB tag)."""

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "S-SLAB",
        boundary: Optional[List[Tuple[float, float]]] = None,
        thickness: float = 0.2,
        elevation: float = 0.0,
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "S-SLAB", properties=properties)
        self.boundary = boundary or []
        self.thickness = thickness
        self.elevation = elevation

    @property
    def area(self) -> float:
        """Calculates 2D planar area using Shoelace formula."""
        n = len(self.boundary)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.boundary[i][0] * self.boundary[j][1]
            area -= self.boundary[j][0] * self.boundary[i][1]
        return abs(area) / 2.0

    @property
    def volume(self) -> float:
        return self.area * self.thickness

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        if not self.boundary:
            return ((0.0, 0.0, self.elevation), (0.0, 0.0, self.elevation + self.thickness))
        min_x = min(p[0] for p in self.boundary)
        max_x = max(p[0] for p in self.boundary)
        min_y = min(p[1] for p in self.boundary)
        max_y = max(p[1] for p in self.boundary)
        min_z = self.elevation
        max_z = self.elevation + self.thickness
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "boundary": self.boundary,
                "thickness": self.thickness,
                "elevation": self.elevation,
                "area": self.area,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Stair(GeometryObject):
    """
    Parametric Stair object (A-STAIR tag).
    Generates parametric steps (risers, treads, and landing plates).
    """

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "A-STAIR",
        start: Tuple[float, float] = (0.0, 0.0),
        end: Optional[Tuple[float, float]] = None,
        width: float = 1.0,
        height: float = 3.0,
        num_steps: int = 16,
        landing_depth: float = 0.0,
        landing_thickness: float = 0.15,
        elevation: float = 0.0,
        stair_type: str = "straight",
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "A-STAIR", properties=properties)
        self.start = start
        self.width = width
        self.height = height
        self.num_steps = max(1, int(num_steps))
        self.landing_depth = landing_depth
        self.landing_thickness = landing_thickness
        self.elevation = elevation
        self.stair_type = stair_type.lower() if stair_type else "straight"

        if end is not None:
            self.end = end
        else:
            default_run = self.num_steps * 0.28 + self.landing_depth
            self.end = (self.start[0] + default_run, self.start[1])

    @property
    def riser_height(self) -> float:
        return self.height / self.num_steps

    @property
    def total_run(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return math.hypot(dx, dy)

    @property
    def tread_depth(self) -> float:
        run_for_steps = max(0.0, self.total_run - self.landing_depth)
        return run_for_steps / self.num_steps if self.num_steps > 0 else 0.28

    @property
    def volume(self) -> float:
        step_vol = sum(self.width * self.tread_depth * (self.riser_height * (i + 1)) for i in range(self.num_steps))
        landing_vol = self.width * self.landing_depth * self.landing_thickness
        return step_vol + landing_vol

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        len_val = self.total_run
        if len_val == 0:
            nx, ny = 0.0, 0.0
        else:
            nx, ny = -dy / len_val * (self.width / 2.0), dx / len_val * (self.width / 2.0)

        corners = [
            (self.start[0] + nx, self.start[1] + ny),
            (self.start[0] - nx, self.start[1] - ny),
            (self.end[0] + nx, self.end[1] + ny),
            (self.end[0] - nx, self.end[1] - ny),
        ]

        min_x = min(p[0] for p in corners)
        max_x = max(p[0] for p in corners)
        min_y = min(p[1] for p in corners)
        max_y = max(p[1] for p in corners)
        min_z = self.elevation
        max_z = self.elevation + self.height
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "start": self.start,
                "end": self.end,
                "width": self.width,
                "height": self.height,
                "num_steps": self.num_steps,
                "riser_height": self.riser_height,
                "tread_depth": self.tread_depth,
                "landing_depth": self.landing_depth,
                "landing_thickness": self.landing_thickness,
                "elevation": self.elevation,
                "stair_type": self.stair_type,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Space(GeometryObject):
    """
    Architectural Space / Zone object (A-SPACE tag).
    Calculates room net floor area (m²) and air volume (m³).
    """

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "A-SPACE",
        boundary: Optional[List[Tuple[float, float]]] = None,
        height: float = 3.0,
        elevation: float = 0.0,
        number: str = "",
        zone: str = "",
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "A-SPACE", properties=properties)
        self.boundary = boundary or []
        self.height = height
        self.elevation = elevation
        self.number = number
        self.zone = zone

    @property
    def area(self) -> float:
        """Calculates room net floor area (m²) using Shoelace formula."""
        n = len(self.boundary)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += self.boundary[i][0] * self.boundary[j][1]
            area -= self.boundary[j][0] * self.boundary[i][1]
        return abs(area) / 2.0

    @property
    def volume(self) -> float:
        """Calculates room air volume (m³)."""
        return self.area * self.height

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        if not self.boundary:
            return ((0.0, 0.0, self.elevation), (0.0, 0.0, self.elevation + self.height))
        min_x = min(p[0] for p in self.boundary)
        max_x = max(p[0] for p in self.boundary)
        min_y = min(p[1] for p in self.boundary)
        max_y = max(p[1] for p in self.boundary)
        min_z = self.elevation
        max_z = self.elevation + self.height
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "boundary": self.boundary,
                "height": self.height,
                "elevation": self.elevation,
                "number": self.number,
                "zone": self.zone,
                "area": self.area,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Door(GeometryObject):
    """
    Parametric Door component entity with 3D frames and panel (A-DOOR tag).
    """

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "A-DOOR",
        position: Tuple[float, float] = (0.0, 0.0),
        width: float = 0.9,
        height: float = 2.1,
        sill_height: float = 0.0,
        depth: float = 0.1,
        frame_width: float = 0.05,
        panel_thickness: float = 0.04,
        elevation: float = 0.0,
        direction: float = 0.0,
        door_type: str = "single",
        host_wall_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "A-DOOR", properties=properties)
        self.position = position
        self.width = width
        self.height = height
        self.sill_height = sill_height
        self.depth = depth
        self.frame_width = frame_width
        self.panel_thickness = panel_thickness
        self.elevation = elevation
        self.direction = direction
        self.door_type = door_type
        self.host_wall_id = host_wall_id

    @property
    def volume(self) -> float:
        """Volume of 3D door frame and door panel."""
        w_inner = max(0.0, self.width - 2 * self.frame_width)
        h_inner = max(0.0, self.height - self.frame_width)
        frame_vol = (self.width * self.depth * self.frame_width) + (2 * h_inner * self.depth * self.frame_width)
        panel_vol = w_inner * self.panel_thickness * h_inner
        return frame_vol + panel_vol

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        x, y = self.position
        z_min = self.elevation + self.sill_height
        z_max = z_min + self.height
        rad = math.radians(self.direction)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        hw, hd = self.width / 2.0, self.depth / 2.0
        local_corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
        rot_corners = [(x + cx * cos_a - cy * sin_a, y + cx * sin_a + cy * cos_a) for cx, cy in local_corners]

        min_x = min(p[0] for p in rot_corners)
        max_x = max(p[0] for p in rot_corners)
        min_y = min(p[1] for p in rot_corners)
        max_y = max(p[1] for p in rot_corners)
        return ((min_x, min_y, z_min), (max_x, max_y, z_max))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "position": self.position,
                "width": self.width,
                "height": self.height,
                "sill_height": self.sill_height,
                "depth": self.depth,
                "frame_width": self.frame_width,
                "panel_thickness": self.panel_thickness,
                "elevation": self.elevation,
                "direction": self.direction,
                "door_type": self.door_type,
                "host_wall_id": self.host_wall_id,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Window(GeometryObject):
    """
    Parametric Window component entity with 3D frames and glazed panels (A-WINDOW tag).
    """

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "A-WINDOW",
        position: Tuple[float, float] = (0.0, 0.0),
        width: float = 1.2,
        height: float = 1.5,
        sill_height: float = 0.9,
        depth: float = 0.1,
        frame_width: float = 0.05,
        glass_thickness: float = 0.01,
        elevation: float = 0.0,
        direction: float = 0.0,
        window_type: str = "casement",
        host_wall_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "A-WINDOW", properties=properties)
        self.position = position
        self.width = width
        self.height = height
        self.sill_height = sill_height
        self.depth = depth
        self.frame_width = frame_width
        self.glass_thickness = glass_thickness
        self.elevation = elevation
        self.direction = direction
        self.window_type = window_type
        self.host_wall_id = host_wall_id

    @property
    def volume(self) -> float:
        """Volume of 3D window frame and glazed glass panel."""
        w_inner = max(0.0, self.width - 2 * self.frame_width)
        h_inner = max(0.0, self.height - 2 * self.frame_width)
        frame_vol = (2 * self.width * self.depth * self.frame_width) + (2 * h_inner * self.depth * self.frame_width)
        glass_vol = w_inner * self.glass_thickness * h_inner
        return frame_vol + glass_vol

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        x, y = self.position
        z_min = self.elevation + self.sill_height
        z_max = z_min + self.height
        rad = math.radians(self.direction)
        cos_a, sin_a = math.cos(rad), math.sin(rad)

        hw, hd = self.width / 2.0, self.depth / 2.0
        local_corners = [(-hw, -hd), (hw, -hd), (hw, hd), (-hw, hd)]
        rot_corners = [(x + cx * cos_a - cy * sin_a, y + cx * sin_a + cy * cos_a) for cx, cy in local_corners]

        min_x = min(p[0] for p in rot_corners)
        max_x = max(p[0] for p in rot_corners)
        min_y = min(p[1] for p in rot_corners)
        max_y = max(p[1] for p in rot_corners)
        return ((min_x, min_y, z_min), (max_x, max_y, z_max))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "position": self.position,
                "width": self.width,
                "height": self.height,
                "sill_height": self.sill_height,
                "depth": self.depth,
                "frame_width": self.frame_width,
                "glass_thickness": self.glass_thickness,
                "elevation": self.elevation,
                "direction": self.direction,
                "window_type": self.window_type,
                "host_wall_id": self.host_wall_id,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Opening:
    """Opening in wall volume (doors, windows, voids)."""

    def __init__(
        self,
        id_str: str,
        offset: float = 0.0,
        width: float = 1.0,
        height: float = 2.0,
        sill_height: float = 0.0,
        opening_type: str = "opening",
    ):
        self.id = id_str
        self.offset = offset
        self.width = width
        self.height = height
        self.sill_height = sill_height
        self.opening_type = opening_type

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "offset": self.offset,
            "width": self.width,
            "height": self.height,
            "sill_height": self.sill_height,
            "type": self.opening_type,
        }


class Wall(GeometryObject):
    """Extruded Wall Volume with support for openings (A-WALL tag)."""

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "A-WALL",
        start: Tuple[float, float] = (0.0, 0.0),
        end: Tuple[float, float] = (1.0, 0.0),
        thickness: float = 0.2,
        height: float = 3.0,
        elevation: float = 0.0,
        openings: Optional[List[Opening]] = None,
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "A-WALL", properties=properties)
        self.start = start
        self.end = end
        self.thickness = thickness
        self.height = height
        self.elevation = elevation
        self.openings: List[Opening] = openings or []

    @property
    def length(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return math.hypot(dx, dy)

    @property
    def gross_volume(self) -> float:
        return self.length * self.thickness * self.height

    @property
    def net_volume(self) -> float:
        opening_volume = sum(op.width * op.height * self.thickness for op in self.openings)
        return max(0.0, self.gross_volume - opening_volume)

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        len_val = self.length
        if len_val == 0:
            nx, ny = 0.0, 0.0
        else:
            nx, ny = -dy / len_val * (self.thickness / 2.0), dx / len_val * (self.thickness / 2.0)

        corners = [
            (self.start[0] + nx, self.start[1] + ny),
            (self.start[0] - nx, self.start[1] - ny),
            (self.end[0] + nx, self.end[1] + ny),
            (self.end[0] - nx, self.end[1] - ny),
        ]

        min_x = min(p[0] for p in corners)
        max_x = max(p[0] for p in corners)
        min_y = min(p[1] for p in corners)
        max_y = max(p[1] for p in corners)
        min_z = self.elevation
        max_z = self.elevation + self.height
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "start": self.start,
                "end": self.end,
                "length": self.length,
                "thickness": self.thickness,
                "height": self.height,
                "elevation": self.elevation,
                "gross_volume": self.gross_volume,
                "net_volume": self.net_volume,
                "openings": [op.to_dict() for op in self.openings],
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Column(GeometryObject):
    """Reusable Component Instance representing columns (S-COLS tag)."""

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "S-COLS",
        position: Tuple[float, float] = (0.0, 0.0),
        section: Tuple[float, float] = (0.3, 0.3),
        radius: Optional[float] = None,
        height: float = 3.0,
        elevation: float = 0.0,
        profile: str = "rectangular",
        component: str = "StandardColumn",
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "S-COLS", properties=properties)
        self.position = position
        self.section = section
        self.radius = radius
        self.height = height
        self.elevation = elevation
        self.profile = profile
        self.component = component

    @property
    def volume(self) -> float:
        if self.profile == "circular" or self.radius is not None:
            r = self.radius if self.radius is not None else self.section[0] / 2.0
            return math.pi * (r ** 2) * self.height
        return self.section[0] * self.section[1] * self.height

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        x, y = self.position
        if self.profile == "circular" or self.radius is not None:
            r = self.radius if self.radius is not None else self.section[0] / 2.0
            half_w, half_d = r, r
        else:
            half_w, half_d = self.section[0] / 2.0, self.section[1] / 2.0

        min_x, max_x = x - half_w, x + half_w
        min_y, max_y = y - half_d, y + half_d
        min_z, max_z = self.elevation, self.elevation + self.height
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "position": self.position,
                "section": self.section,
                "radius": self.radius,
                "height": self.height,
                "elevation": self.elevation,
                "profile": self.profile,
                "component": self.component,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Beam(GeometryObject):
    """Component Instance representing structural beams (S-BEAM tag)."""

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "S-BEAM",
        start: Tuple[float, float] = (0.0, 0.0),
        end: Tuple[float, float] = (1.0, 0.0),
        width: float = 0.2,
        depth: float = 0.4,
        elevation: float = 0.0,
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "S-BEAM", properties=properties)
        self.start = start
        self.end = end
        self.width = width
        self.depth = depth
        self.elevation = elevation

    @property
    def length(self) -> float:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        return math.hypot(dx, dy)

    @property
    def volume(self) -> float:
        return self.length * self.width * self.depth

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        dx = self.end[0] - self.start[0]
        dy = self.end[1] - self.start[1]
        len_val = math.hypot(dx, dy)
        if len_val == 0:
            nx, ny = 0.0, 0.0
        else:
            nx, ny = -dy / len_val * (self.width / 2.0), dx / len_val * (self.width / 2.0)

        corners = [
            (self.start[0] + nx, self.start[1] + ny),
            (self.start[0] - nx, self.start[1] - ny),
            (self.end[0] + nx, self.end[1] + ny),
            (self.end[0] - nx, self.end[1] - ny),
        ]

        min_x = min(p[0] for p in corners)
        max_x = max(p[0] for p in corners)
        min_y = min(p[1] for p in corners)
        max_y = max(p[1] for p in corners)
        min_z = min(self.elevation, self.elevation + self.depth)
        max_z = max(self.elevation, self.elevation + self.depth)
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "start": self.start,
                "end": self.end,
                "length": self.length,
                "width": self.width,
                "depth": self.depth,
                "elevation": self.elevation,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Footing(GeometryObject):
    """Structural Footing or Pile Cap object (S-FOOTING tag)."""

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "S-FOOTING",
        position: Tuple[float, float] = (0.0, 0.0),
        section: Tuple[float, float] = (1.0, 1.0),
        thickness: float = 0.4,
        elevation: float = 0.0,
        footing_type: str = "isolated",
        column_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "S-FOOTING", properties=properties)
        self.position = position
        self.section = section
        self.thickness = thickness
        self.elevation = elevation
        self.footing_type = footing_type
        self.column_id = column_id

    @property
    def volume(self) -> float:
        return self.section[0] * self.section[1] * self.thickness

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        x, y = self.position
        hw, hd = self.section[0] / 2.0, self.section[1] / 2.0
        min_x, max_x = x - hw, x + hw
        min_y, max_y = y - hd, y + hd
        min_z = min(self.elevation, self.elevation + self.thickness)
        max_z = max(self.elevation, self.elevation + self.thickness)
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "position": self.position,
                "section": self.section,
                "thickness": self.thickness,
                "elevation": self.elevation,
                "footing_type": self.footing_type,
                "column_id": self.column_id,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class Roof(GeometryObject):
    """Architectural Roof object with sloping pitch faces and eaves overhang (A-ROOF tag)."""

    def __init__(
        self,
        id_str: str,
        name: str = "",
        tag: str = "A-ROOF",
        boundary: Optional[List[Tuple[float, float]]] = None,
        roof_type: str = "gable",
        pitch: float = 30.0,
        overhang: float = 0.5,
        thickness: float = 0.2,
        elevation: float = 0.0,
        ridge_direction: str = "X",
        properties: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(id_str, name=name, tag=tag or "A-ROOF", properties=properties)
        self.boundary = boundary or []
        self.roof_type = roof_type.lower() if roof_type else "gable"
        self.pitch = float(pitch)
        self.overhang = float(overhang)
        self.thickness = float(thickness)
        self.elevation = float(elevation)
        self.ridge_direction = ridge_direction.upper() if ridge_direction else "X"

    @property
    def eaves_boundary(self) -> List[Tuple[float, float]]:
        """Calculates boundary expanded by overhang distance."""
        if not self.boundary:
            return []
        min_x = min(p[0] for p in self.boundary)
        max_x = max(p[0] for p in self.boundary)
        min_y = min(p[1] for p in self.boundary)
        max_y = max(p[1] for p in self.boundary)
        ov = self.overhang
        return [
            (min_x - ov, min_y - ov),
            (max_x + ov, min_y - ov),
            (max_x + ov, max_y + ov),
            (min_x - ov, max_y + ov),
        ]

    @property
    def area(self) -> float:
        """Calculates 2D planar area of eaves boundary using Shoelace formula."""
        poly = self.eaves_boundary or self.boundary
        n = len(poly)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += poly[i][0] * poly[j][1]
            area -= poly[j][0] * poly[i][1]
        return abs(area) / 2.0

    @property
    def volume(self) -> float:
        return self.area * self.thickness

    def get_3d_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        poly = self.eaves_boundary or self.boundary
        if not poly:
            return ((0.0, 0.0, self.elevation), (0.0, 0.0, self.elevation + self.thickness))
        min_x = min(p[0] for p in poly)
        max_x = max(p[0] for p in poly)
        min_y = min(p[1] for p in poly)
        max_y = max(p[1] for p in poly)
        min_z = self.elevation

        w_x = max_x - min_x
        w_y = max_y - min_y
        pitch_rad = math.radians(self.pitch)

        if self.roof_type == "flat":
            h_ridge = 0.0
        elif self.roof_type == "shed":
            span = w_x if self.ridge_direction == "X" else w_y
            h_ridge = span * math.tan(pitch_rad)
        elif self.roof_type == "hip":
            span = min(w_x, w_y) / 2.0
            h_ridge = span * math.tan(pitch_rad)
        else:  # gable
            span = (w_y / 2.0) if self.ridge_direction == "X" else (w_x / 2.0)
            h_ridge = span * math.tan(pitch_rad)

        max_z = self.elevation + h_ridge + self.thickness
        return ((min_x, min_y, min_z), (max_x, max_y, max_z))

    def to_dict(self) -> Dict[str, Any]:
        res = super().to_dict()
        res.update(
            {
                "boundary": self.boundary,
                "eaves_boundary": self.eaves_boundary,
                "roof_type": self.roof_type,
                "pitch": self.pitch,
                "overhang": self.overhang,
                "thickness": self.thickness,
                "elevation": self.elevation,
                "ridge_direction": self.ridge_direction,
                "area": self.area,
                "volume": self.volume,
                "bounds": self.get_3d_bounds(),
            }
        )
        return res


class BuildingModel:
    """Root representation of the entire loaded .debim model."""

    def __init__(
        self,
        name: str = "Untitled Project",
        units: str = "m",
        origin: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ):
        self.name = name
        self.units = units
        self.origin = origin
        self.unit_scale = self._calc_unit_scale(units)
        self.root_group = Group("ROOT", name=name)
        self.storeys: List[Group] = []

    @staticmethod
    def _calc_unit_scale(units: Union[str, Dict[str, Any]]) -> float:
        if isinstance(units, dict):
            u_str = str(units.get("length") or units.get("length_unit") or "m")
        elif isinstance(units, str):
            u_str = units
        else:
            u_str = "m"

        u = u_str.lower().strip()
        if u in ("m", "meter", "meters", "square_meter", "cubic_meter"):
            return 1.0
        elif u in ("mm", "millimeter", "millimeters"):
            return 0.001
        elif u in ("cm", "centimeter", "centimeters"):
            return 0.01
        elif u in ("ft", "feet", "foot"):
            return 0.3048
        elif u in ("in", "inch", "inches"):
            return 0.0254
        return 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "units": self.units,
            "origin": self.origin,
            "unit_scale": self.unit_scale,
            "model": self.root_group.to_dict(),
        }


def build_geometry(manifest_data: Dict[str, Any]) -> BuildingModel:
    """
    Constructs native 3D geometry objects from a parsed .debim manifest.
    Supports both standard IFC4-Minimal elements and simplified schema modes.
    """
    proj_info = manifest_data.get("project", {}) or {}
    bldg_info = manifest_data.get("building", {}) or {}

    proj_name = proj_info.get("name") or bldg_info.get("name") or "Debim Building"
    units = proj_info.get("units") or "m"
    raw_origin = proj_info.get("origin", [0.0, 0.0, 0.0])
    if isinstance(raw_origin, (list, tuple)) and len(raw_origin) >= 3:
        origin = (float(raw_origin[0]), float(raw_origin[1]), float(raw_origin[2]))
    else:
        origin = (0.0, 0.0, 0.0)

    model = BuildingModel(name=proj_name, units=units, origin=origin)
    scale = model.unit_scale
    ox, oy, oz = origin

    # Initialize GridSystem
    grids_data = manifest_data.get("grids") or {}
    grid_sys = GridSystem(grids_data)
    model.grid_system = grid_sys

    # Read storeys / spatial structure
    spatial = manifest_data.get("spatial_structure") or {}
    storeys_data = (
        spatial.get("storeys")
        or spatial.get("building", {}).get("storeys")
        or bldg_info.get("storeys")
        or manifest_data.get("storeys")
        or []
    )

    if not storeys_data and ("slabs" in manifest_data or "walls" in manifest_data or "columns" in manifest_data or "beams" in manifest_data or "footings" in manifest_data or "roofs" in manifest_data or "stairs" in manifest_data or "spaces" in manifest_data or "doors" in manifest_data or "windows" in manifest_data or "rooms" in manifest_data or "zones" in manifest_data or "elements" in manifest_data):
        storeys_data = [{
            "id": "DEFAULT_STOREY",
            "name": "Default Level",
            "elevation": 0.0,
            "height": 3.0,
        }]

    storey_groups_map: Dict[str, Group] = {}

    for idx, st in enumerate(storeys_data):
        st_id = str(st.get("id", f"STOREY_{idx+1}"))
        st_name = str(st.get("name", f"Level {idx+1}"))
        st_elev = float(st.get("elevation", 0.0)) * scale + oz
        st_height = float(st.get("height", 3.0)) * scale

        storey_group = Group(
            id_str=st_id,
            name=st_name,
            tag="A-STOREY",
            elevation=st_elev,
            height=st_height,
            properties=st.get("properties"),
        )
        model.storeys.append(storey_group)
        model.root_group.add_child(storey_group)
        storey_groups_map[st_id] = storey_group

    # Extract all elements
    all_elements = extract_elements(manifest_data)

    # First pass: build all Column objects and index them for Footing auto-placement lookup
    columns_map: Dict[str, Column] = {}
    for idx, elem in enumerate(all_elements):
        cls_str = f"{elem.get('class') or ''} {elem.get('category') or ''} {elem.get('type') or ''}".lower()
        if "col" in cls_str or "ifccolumn" in cls_str:
            placement = elem.get("placement") or {}
            st_target = placement.get("storey") or elem.get("storey") if isinstance(placement, dict) else elem.get("storey")
            target_group = storey_groups_map.get(str(st_target)) if st_target else (model.storeys[0] if model.storeys else None)
            if target_group is not None:
                st_elev = target_group.elevation
                st_height = target_group.height
                col_obj = _build_column(elem, idx, st_elev, st_height, scale, ox, oy, grid_sys)
                columns_map[col_obj.id] = col_obj
                columns_map[col_obj.name] = col_obj
                if col_obj.tag:
                    columns_map[col_obj.tag] = col_obj

    # Second pass: process all extracted elements
    for idx, elem in enumerate(all_elements):
        placement = elem.get("placement") or {}
        st_target = None
        if isinstance(placement, dict):
            st_target = placement.get("storey") or elem.get("storey")
        else:
            st_target = elem.get("storey")

        target_group = None
        if st_target and str(st_target) in storey_groups_map:
            target_group = storey_groups_map[str(st_target)]
        elif model.storeys:
            target_group = model.storeys[0]

        if target_group is None:
            continue

        st_elev = target_group.elevation
        st_height = target_group.height

        cls_str = f"{elem.get('class') or ''} {elem.get('category') or ''} {elem.get('type') or ''}".lower()

        if "col" in cls_str or "ifccolumn" in cls_str:
            # Look up previously built column from columns_map
            c_id = str(elem.get("id") or elem.get("tag") or f"COL_{idx+1}")
            col_obj = columns_map.get(c_id)
            if col_obj and col_obj not in target_group.children:
                target_group.add_child(col_obj)
        elif "footing" in cls_str or "ifcfooting" in cls_str or "pile" in cls_str:
            footing_obj = _build_footing(elem, idx, st_elev, scale, ox, oy, grid_sys, columns_map=columns_map)
            target_group.add_child(footing_obj)
        elif "roof" in cls_str or "ifcroof" in cls_str:
            roof_obj = _build_roof(elem, idx, st_elev, scale, ox, oy, grid_sys)
            target_group.add_child(roof_obj)
        elif "stair" in cls_str or "ifcstair" in cls_str:
            stair_obj = _build_stair(elem, idx, st_elev, st_height, scale, ox, oy, grid_sys)
            target_group.add_child(stair_obj)
        elif "space" in cls_str or "ifcspace" in cls_str or "room" in cls_str or "zone" in cls_str:
            space_obj = _build_space(elem, idx, st_elev, st_height, scale, ox, oy, grid_sys)
            target_group.add_child(space_obj)
        elif "door" in cls_str or "ifcdoor" in cls_str:
            door_obj = _build_door(elem, idx, st_elev, scale, ox, oy, grid_sys)
            target_group.add_child(door_obj)
        elif "window" in cls_str or "ifcwindow" in cls_str:
            window_obj = _build_window(elem, idx, st_elev, scale, ox, oy, grid_sys)
            target_group.add_child(window_obj)
        elif "wall" in cls_str or "ifcwall" in cls_str:
            wall_obj = _build_wall(elem, idx, st_elev, st_height, scale, ox, oy, grid_sys)
            target_group.add_child(wall_obj)
        elif "slab" in cls_str or "ifcslab" in cls_str:
            slab_obj = _build_slab(elem, idx, st_elev, scale, ox, oy, grid_sys)
            target_group.add_child(slab_obj)
        elif "beam" in cls_str or "ifcbeam" in cls_str:
            beam_obj = _build_beam(elem, idx, st_elev, scale, ox, oy, grid_sys)
            target_group.add_child(beam_obj)

    return model


def _build_footing(
    ft: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
    columns_map: Optional[Dict[str, Column]] = None,
) -> Footing:
    grid_sys = grid_sys or GridSystem()
    columns_map = columns_map or {}
    placement = ft.get("placement") or {}
    f_id = str(ft.get("id") or ft.get("tag") or f"FOOTING_{idx+1}")
    f_name = str(ft.get("name") or f_id)
    tag = str(ft.get("tag") or "S-FOOTING")

    thickness = float(ft.get("thickness") or ft.get("depth") or ft.get("height") or 0.4) * scale

    prof = ft.get("profile") or ft.get("section") or {}
    if isinstance(prof, dict):
        w = float(prof.get("width") or prof.get("b") or prof.get("x", 1.0)) * scale
        d = float(prof.get("depth") or prof.get("length") or prof.get("h") or prof.get("y", w / scale)) * scale
        section = (w, d)
    elif isinstance(prof, (list, tuple)) and len(prof) >= 2:
        section = (float(prof[0]) * scale, float(prof[1]) * scale)
    else:
        w = float(ft.get("width", ft.get("b", 1.0))) * scale
        d = float(ft.get("depth", ft.get("length", ft.get("h", w / scale)))) * scale
        section = (w, d)

    raw_type = str(ft.get("footing_type") or ft.get("type") or ft.get("shape") or "isolated").lower()
    if "pile" in raw_type:
        footing_type = "pile_cap"
    else:
        footing_type = "isolated"

    col_id = ft.get("column_id") or ft.get("column") or placement.get("column") or placement.get("column_id")
    col_obj = columns_map.get(str(col_id)) if col_id and str(col_id) in columns_map else None

    if col_obj is not None:
        position = col_obj.position
        if "elevation" in ft or "elevation" in placement or "offset" in ft:
            local_offset = float(ft.get("offset") or ft.get("elevation") or placement.get("elevation") or 0.0) * scale
            abs_elevation = storey_elevation + local_offset
        else:
            abs_elevation = col_obj.elevation - thickness
    else:
        grid_spec = placement.get("grid") or ft.get("grid") or placement.get("position") or ft.get("position") or ft.get("location")
        if grid_spec is not None:
            p_res = grid_sys.resolve_point(grid_spec)
            position = (p_res[0] * scale + ox, p_res[1] * scale + oy)
        else:
            position = (0.0, 0.0)

        local_offset = float(ft.get("offset") or ft.get("elevation") or placement.get("elevation") or 0.0) * scale
        abs_elevation = storey_elevation + local_offset

    return Footing(
        id_str=f_id,
        name=f_name,
        tag=tag,
        position=position,
        section=section,
        thickness=thickness,
        elevation=abs_elevation,
        footing_type=footing_type,
        column_id=str(col_id) if col_id else None,
        properties=ft.get("properties"),
    )


def _build_roof(
    rf: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Roof:
    grid_sys = grid_sys or GridSystem()
    placement = rf.get("placement") or {}
    r_id = str(rf.get("id") or rf.get("tag") or f"ROOF_{idx+1}")
    r_name = str(rf.get("name") or r_id)
    tag = str(rf.get("tag") or "A-ROOF")

    raw_roof_type = str(rf.get("roof_type") or rf.get("type") or "gable").lower()
    if "gable" in raw_roof_type or "จั่ว" in raw_roof_type:
        roof_type = "gable"
    elif "hip" in raw_roof_type or "ปั้นหยา" in raw_roof_type:
        roof_type = "hip"
    elif "shed" in raw_roof_type or "เพิง" in raw_roof_type or "skillion" in raw_roof_type:
        roof_type = "shed"
    elif "flat" in raw_roof_type or "ดาดฟ้า" in raw_roof_type:
        roof_type = "flat"
    else:
        roof_type = "gable"

    pitch = float(rf.get("pitch") or rf.get("pitch_angle") or rf.get("angle") or (0.0 if roof_type == "flat" else 30.0))
    overhang = float(rf.get("overhang") or rf.get("eaves") or 0.5) * scale
    thickness = float(rf.get("thickness") or rf.get("depth") or 0.2) * scale

    local_offset = float(rf.get("offset") or rf.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    ridge_direction = str(rf.get("ridge_direction") or rf.get("direction") or "X").upper()

    raw_boundary = (
        rf.get("boundary")
        or rf.get("polygon")
        or rf.get("points")
        or placement.get("boundary")
        or []
    )

    boundary: List[Tuple[float, float]] = []
    if raw_boundary:
        for pt in raw_boundary:
            p_res = grid_sys.resolve_point(pt)
            boundary.append((p_res[0] * scale + ox, p_res[1] * scale + oy))
    else:
        from_g = placement.get("from_grid") or rf.get("from_grid")
        to_g = placement.get("to_grid") or rf.get("to_grid")
        if from_g and to_g:
            p1 = grid_sys.resolve_point(from_g)
            p2 = grid_sys.resolve_point(to_g)
            boundary = [
                (p1[0] * scale + ox, p1[1] * scale + oy),
                (p2[0] * scale + ox, p1[1] * scale + oy),
                (p2[0] * scale + ox, p2[1] * scale + oy),
                (p1[0] * scale + ox, p2[1] * scale + oy),
            ]
        else:
            w = float(rf.get("width", 10.0)) * scale
            d = float(rf.get("depth", 8.0)) * scale
            boundary = [
                (ox, oy),
                (ox + w, oy),
                (ox + w, oy + d),
                (ox, oy + d),
            ]

    return Roof(
        id_str=r_id,
        name=r_name,
        tag=tag,
        boundary=boundary,
        roof_type=roof_type,
        pitch=pitch,
        overhang=overhang,
        thickness=thickness,
        elevation=abs_elevation,
        ridge_direction=ridge_direction,
        properties=rf.get("properties"),
    )


def _build_slab(
    sl: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Slab:
    grid_sys = grid_sys or GridSystem()
    placement = sl.get("placement") or {}
    s_id = str(sl.get("id") or sl.get("tag") or f"SLAB_{idx+1}")
    s_name = str(sl.get("name") or s_id)
    cls_type = str(sl.get("class") or sl.get("category") or "").lower()
    tag = str(sl.get("tag") or ("S-FOOTING" if "footing" in cls_type else "S-SLAB"))

    thickness = float(sl.get("thickness") or sl.get("depth") or 0.2) * scale
    local_offset = float(sl.get("offset") or sl.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    raw_boundary = (
        sl.get("boundary")
        or sl.get("polygon")
        or sl.get("points")
        or placement.get("boundary")
        or []
    )

    boundary: List[Tuple[float, float]] = []
    if raw_boundary:
        for pt in raw_boundary:
            p_res = grid_sys.resolve_point(pt)
            boundary.append((p_res[0] * scale + ox, p_res[1] * scale + oy))
    else:
        from_g = placement.get("from_grid") or sl.get("from_grid")
        to_g = placement.get("to_grid") or sl.get("to_grid")
        if from_g and to_g:
            p1 = grid_sys.resolve_point(from_g)
            p2 = grid_sys.resolve_point(to_g)
            boundary = [
                (p1[0] * scale + ox, p1[1] * scale + oy),
                (p2[0] * scale + ox, p1[1] * scale + oy),
                (p2[0] * scale + ox, p2[1] * scale + oy),
                (p1[0] * scale + ox, p2[1] * scale + oy),
            ]
        else:
            g_pt = placement.get("grid") or sl.get("grid") or placement.get("position") or sl.get("position")
            if g_pt:
                cx, cy = grid_sys.resolve_point(g_pt)
                hw = float(sl.get("width", 1.0)) / 2.0
                hd = float(sl.get("depth", 1.0)) / 2.0
                boundary = [
                    ((cx - hw) * scale + ox, (cy - hd) * scale + oy),
                    ((cx + hw) * scale + ox, (cy - hd) * scale + oy),
                    ((cx + hw) * scale + ox, (cy + hd) * scale + oy),
                    ((cx - hw) * scale + ox, (cy + hd) * scale + oy),
                ]

    return Slab(
        id_str=s_id,
        name=s_name,
        tag=tag,
        boundary=boundary,
        thickness=thickness,
        elevation=abs_elevation,
        properties=sl.get("properties"),
    )


def _build_wall(
    wl: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    default_height: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Wall:
    grid_sys = grid_sys or GridSystem()
    placement = wl.get("placement") or {}
    w_id = str(wl.get("id") or wl.get("tag") or f"WALL_{idx+1}")
    w_name = str(wl.get("name") or w_id)
    tag = str(wl.get("tag") or "A-WALL")
    thickness = float(wl.get("thickness") or wl.get("width") or 0.2) * scale
    height = float(wl.get("height") or (default_height / scale)) * scale
    local_offset = float(wl.get("offset") or wl.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    from_g = placement.get("from_grid") or wl.get("from_grid") or wl.get("start")
    to_g = placement.get("to_grid") or wl.get("to_grid") or wl.get("end")

    if from_g is not None and to_g is not None:
        p1 = grid_sys.resolve_point(from_g)
        p2 = grid_sys.resolve_point(to_g)
    else:
        p1 = (0.0, 0.0)
        p2 = (1.0, 0.0)

    start = (p1[0] * scale + ox, p1[1] * scale + oy)
    end = (p2[0] * scale + ox, p2[1] * scale + oy)

    openings_data = wl.get("openings") or wl.get("voids") or []
    openings: List[Opening] = []
    for op_idx, op in enumerate(openings_data):
        op_id = str(op.get("id", f"OPENING_{op_idx+1}"))
        op_offset = float(op.get("offset", 0.0)) * scale
        op_width = float(op.get("width", 1.0)) * scale
        op_height = float(op.get("height", 2.0)) * scale
        op_sill = float(op.get("sill_height", op.get("sill", 0.0))) * scale
        op_type = str(op.get("type", op.get("category", "opening")))
        openings.append(
            Opening(
                id_str=op_id,
                offset=op_offset,
                width=op_width,
                height=op_height,
                sill_height=op_sill,
                opening_type=op_type,
            )
        )

    return Wall(
        id_str=w_id,
        name=w_name,
        tag=tag,
        start=start,
        end=end,
        thickness=thickness,
        height=height,
        elevation=abs_elevation,
        openings=openings,
        properties=wl.get("properties"),
    )


def _build_column(
    cl: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    default_height: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Column:
    grid_sys = grid_sys or GridSystem()
    placement = cl.get("placement") or {}
    c_id = str(cl.get("id") or cl.get("tag") or f"COL_{idx+1}")
    c_name = str(cl.get("name") or c_id)
    tag = str(cl.get("tag") or "S-COLS")
    height = float(cl.get("height") or (default_height / scale)) * scale
    local_offset = float(cl.get("offset") or cl.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    grid_spec = placement.get("grid") or cl.get("grid") or placement.get("position") or cl.get("position") or cl.get("location")
    p_res = grid_sys.resolve_point(grid_spec) if grid_spec is not None else (0.0, 0.0)
    position = (p_res[0] * scale + ox, p_res[1] * scale + oy)

    prof = cl.get("profile") or cl.get("section") or {}
    section = (0.3 * scale, 0.3 * scale)
    radius = None
    profile_type = "rectangular"

    if isinstance(prof, dict):
        shape = str(prof.get("shape", "BOX")).upper()
        if shape in ("CIRCULAR", "CIRCLE", "ROUND"):
            profile_type = "circular"
            if "radius" in prof:
                radius = float(prof["radius"]) * scale
            elif "diameter" in prof:
                radius = (float(prof["diameter"]) / 2.0) * scale
            else:
                radius = 0.15 * scale
            section = (radius * 2.0, radius * 2.0)
        else:
            w = float(prof.get("width") or prof.get("b") or 0.3) * scale
            d = float(prof.get("depth") or prof.get("height") or prof.get("h") or w / scale) * scale
            section = (w, d)
            profile_type = "rectangular"
    elif isinstance(prof, (list, tuple)) and len(prof) >= 2:
        section = (float(prof[0]) * scale, float(prof[1]) * scale)
    elif isinstance(prof, (int, float)):
        section = (float(prof) * scale, float(prof) * scale)

    if "radius" in cl and cl["radius"] is not None:
        radius = float(cl["radius"]) * scale
        profile_type = "circular"

    component = str(cl.get("component") or cl.get("type") or "ColumnComponent")

    return Column(
        id_str=c_id,
        name=c_name,
        tag=tag,
        position=position,
        section=section,
        radius=radius,
        height=height,
        elevation=abs_elevation,
        profile=profile_type,
        component=component,
        properties=cl.get("properties"),
    )


def _build_beam(
    bm: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Beam:
    grid_sys = grid_sys or GridSystem()
    placement = bm.get("placement") or {}
    b_id = str(bm.get("id") or bm.get("tag") or f"BEAM_{idx+1}")
    b_name = str(bm.get("name") or b_id)
    tag = str(bm.get("tag") or "S-BEAM")

    prof = bm.get("profile") or bm.get("section") or {}
    if isinstance(prof, dict):
        width = float(prof.get("width") or prof.get("b") or 0.2) * scale
        depth = float(prof.get("depth") or prof.get("height") or prof.get("h") or 0.4) * scale
    elif isinstance(prof, (list, tuple)) and len(prof) >= 2:
        width = float(prof[0]) * scale
        depth = float(prof[1]) * scale
    else:
        width = float(bm.get("width", bm.get("b", 0.2))) * scale
        depth = float(bm.get("depth", bm.get("height", bm.get("h", 0.4)))) * scale

    local_offset = float(bm.get("offset") or bm.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    from_g = placement.get("from_grid") or bm.get("from_grid") or bm.get("start")
    to_g = placement.get("to_grid") or bm.get("to_grid") or bm.get("end")

    if from_g is not None and to_g is not None:
        p1 = grid_sys.resolve_point(from_g)
        p2 = grid_sys.resolve_point(to_g)
    else:
        p1 = (0.0, 0.0)
        p2 = (1.0, 0.0)

    start = (p1[0] * scale + ox, p1[1] * scale + oy)
    end = (p2[0] * scale + ox, p2[1] * scale + oy)

    props = dict(bm.get("properties") or {})
    for key in ("rebar", "rebar_main", "rebar_stirrup", "stirrup", "section_name", "material", "elevation_ref"):
        if key in bm:
            props[key] = bm[key]

    return Beam(
        id_str=b_id,
        name=b_name,
        tag=tag,
        start=start,
        end=end,
        width=width,
        depth=depth,
        elevation=abs_elevation,
        properties=props,
    )


def _build_stair(
    st: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    default_height: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Stair:
    grid_sys = grid_sys or GridSystem()
    placement = st.get("placement") or {}
    s_id = str(st.get("id") or st.get("tag") or f"STAIR_{idx+1}")
    s_name = str(st.get("name") or s_id)
    tag = str(st.get("tag") or "A-STAIR")

    width = float(st.get("width") or 1.0) * scale
    height = float(st.get("height") or st.get("rise") or (default_height / scale)) * scale
    landing_depth = float(st.get("landing_depth") or st.get("landing") or 0.0) * scale
    landing_thickness = float(st.get("landing_thickness") or st.get("thickness") or 0.15) * scale

    raw_steps = st.get("num_steps") or st.get("steps") or st.get("risers")
    if raw_steps is not None:
        num_steps = max(1, int(raw_steps))
    else:
        num_steps = max(1, int(round(height / (0.175 * scale))))

    local_offset = float(st.get("offset") or st.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    stair_type = str(st.get("stair_type") or st.get("type") or "straight")

    from_g = placement.get("from_grid") or st.get("from_grid") or st.get("start")
    to_g = placement.get("to_grid") or st.get("to_grid") or st.get("end")

    if from_g is not None and to_g is not None:
        p1 = grid_sys.resolve_point(from_g)
        p2 = grid_sys.resolve_point(to_g)
        start = (p1[0] * scale + ox, p1[1] * scale + oy)
        end = (p2[0] * scale + ox, p2[1] * scale + oy)
    elif from_g is not None:
        p1 = grid_sys.resolve_point(from_g)
        start = (p1[0] * scale + ox, p1[1] * scale + oy)
        end = None
    else:
        g_pt = placement.get("grid") or st.get("grid") or placement.get("position") or st.get("position")
        if g_pt is not None:
            p1 = grid_sys.resolve_point(g_pt)
            start = (p1[0] * scale + ox, p1[1] * scale + oy)
        else:
            start = (ox, oy)
        end = None

    return Stair(
        id_str=s_id,
        name=s_name,
        tag=tag,
        start=start,
        end=end,
        width=width,
        height=height,
        num_steps=num_steps,
        landing_depth=landing_depth,
        landing_thickness=landing_thickness,
        elevation=abs_elevation,
        stair_type=stair_type,
        properties=st.get("properties"),
    )


def _build_space(
    sp: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    default_height: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Space:
    grid_sys = grid_sys or GridSystem()
    placement = sp.get("placement") or {}
    s_id = str(sp.get("id") or sp.get("tag") or f"SPACE_{idx+1}")
    s_name = str(sp.get("name") or s_id)
    tag = str(sp.get("tag") or "A-SPACE")

    height = float(sp.get("height") or (default_height / scale)) * scale
    number = str(sp.get("number") or sp.get("room_number") or "")
    zone = str(sp.get("zone") or sp.get("category") or "")

    local_offset = float(sp.get("offset") or sp.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    raw_boundary = (
        sp.get("boundary")
        or sp.get("polygon")
        or sp.get("points")
        or placement.get("boundary")
        or []
    )

    boundary: List[Tuple[float, float]] = []
    if raw_boundary:
        for pt in raw_boundary:
            p_res = grid_sys.resolve_point(pt)
            boundary.append((p_res[0] * scale + ox, p_res[1] * scale + oy))
    else:
        from_g = placement.get("from_grid") or sp.get("from_grid")
        to_g = placement.get("to_grid") or sp.get("to_grid")
        if from_g and to_g:
            p1 = grid_sys.resolve_point(from_g)
            p2 = grid_sys.resolve_point(to_g)
            boundary = [
                (p1[0] * scale + ox, p1[1] * scale + oy),
                (p2[0] * scale + ox, p1[1] * scale + oy),
                (p2[0] * scale + ox, p2[1] * scale + oy),
                (p1[0] * scale + ox, p2[1] * scale + oy),
            ]
        else:
            g_pt = placement.get("grid") or sp.get("grid") or placement.get("position") or sp.get("position")
            if g_pt:
                cx, cy = grid_sys.resolve_point(g_pt)
                hw = float(sp.get("width", 4.0)) / 2.0
                hd = float(sp.get("depth", 4.0)) / 2.0
                boundary = [
                    ((cx - hw) * scale + ox, (cy - hd) * scale + oy),
                    ((cx + hw) * scale + ox, (cy - hd) * scale + oy),
                    ((cx + hw) * scale + ox, (cy + hd) * scale + oy),
                    ((cx - hw) * scale + ox, (cy + hd) * scale + oy),
                ]

    return Space(
        id_str=s_id,
        name=s_name,
        tag=tag,
        boundary=boundary,
        height=height,
        elevation=abs_elevation,
        number=number,
        zone=zone,
        properties=sp.get("properties"),
    )


def _build_door(
    dr: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Door:
    grid_sys = grid_sys or GridSystem()
    placement = dr.get("placement") or {}
    d_id = str(dr.get("id") or dr.get("tag") or f"DOOR_{idx+1}")
    d_name = str(dr.get("name") or d_id)
    tag = str(dr.get("tag") or "A-DOOR")

    width = float(dr.get("width") or 0.9) * scale
    height = float(dr.get("height") or 2.1) * scale
    sill_height = float(dr.get("sill_height") or dr.get("sill") or 0.0) * scale
    depth = float(dr.get("depth") or dr.get("thickness") or 0.1) * scale
    frame_width = float(dr.get("frame_width") or 0.05) * scale
    panel_thickness = float(dr.get("panel_thickness") or 0.04) * scale

    local_offset = float(dr.get("offset") or dr.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    direction = float(dr.get("direction") or dr.get("angle") or dr.get("orientation") or 0.0)
    door_type = str(dr.get("door_type") or dr.get("type") or "single")
    host_wall_id = str(dr.get("host_wall_id") or dr.get("wall")) if (dr.get("host_wall_id") or dr.get("wall")) else None

    grid_spec = placement.get("grid") or dr.get("grid") or placement.get("position") or dr.get("position") or dr.get("location")
    if grid_spec is not None:
        p_res = grid_sys.resolve_point(grid_spec)
        position = (p_res[0] * scale + ox, p_res[1] * scale + oy)
    else:
        position = (ox, oy)

    return Door(
        id_str=d_id,
        name=d_name,
        tag=tag,
        position=position,
        width=width,
        height=height,
        sill_height=sill_height,
        depth=depth,
        frame_width=frame_width,
        panel_thickness=panel_thickness,
        elevation=abs_elevation,
        direction=direction,
        door_type=door_type,
        host_wall_id=host_wall_id,
        properties=dr.get("properties"),
    )


def _build_window(
    win: Dict[str, Any],
    idx: int,
    storey_elevation: float,
    scale: float,
    ox: float,
    oy: float,
    grid_sys: Optional[GridSystem] = None,
) -> Window:
    grid_sys = grid_sys or GridSystem()
    placement = win.get("placement") or {}
    w_id = str(win.get("id") or win.get("tag") or f"WIN_{idx+1}")
    w_name = str(win.get("name") or w_id)
    tag = str(win.get("tag") or "A-WINDOW")

    width = float(win.get("width") or 1.2) * scale
    height = float(win.get("height") or 1.5) * scale
    sill_height = float(win.get("sill_height") or win.get("sill") or 0.9) * scale
    depth = float(win.get("depth") or win.get("thickness") or 0.1) * scale
    frame_width = float(win.get("frame_width") or 0.05) * scale
    glass_thickness = float(win.get("glass_thickness") or 0.01) * scale

    local_offset = float(win.get("offset") or win.get("elevation") or placement.get("elevation") or 0.0) * scale
    abs_elevation = storey_elevation + local_offset

    direction = float(win.get("direction") or win.get("angle") or win.get("orientation") or 0.0)
    window_type = str(win.get("window_type") or win.get("type") or "casement")
    host_wall_id = str(win.get("host_wall_id") or win.get("wall")) if (win.get("host_wall_id") or win.get("wall")) else None

    grid_spec = placement.get("grid") or win.get("grid") or placement.get("position") or win.get("position") or win.get("location")
    if grid_spec is not None:
        p_res = grid_sys.resolve_point(grid_spec)
        position = (p_res[0] * scale + ox, p_res[1] * scale + oy)
    else:
        position = (ox, oy)

    return Window(
        id_str=w_id,
        name=w_name,
        tag=tag,
        position=position,
        width=width,
        height=height,
        sill_height=sill_height,
        depth=depth,
        frame_width=frame_width,
        glass_thickness=glass_thickness,
        elevation=abs_elevation,
        direction=direction,
        window_type=window_type,
        host_wall_id=host_wall_id,
        properties=win.get("properties"),
    )
