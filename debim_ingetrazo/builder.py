"""
3D Entity Geometry Builder for debim-ingetrazo.
Converts parsed .debim manifest structures into native IngeTrazo 3D geometry objects.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Union


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
    def _calc_unit_scale(units: str) -> float:
        u = units.lower().strip()
        if u in ("m", "meter", "meters"):
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
    """
    proj_info = manifest_data.get("project", {}) or {}
    bldg_info = manifest_data.get("building", {}) or {}

    proj_name = proj_info.get("name") or bldg_info.get("name") or "Debim Building"
    units = proj_info.get("units", "m")
    raw_origin = proj_info.get("origin", [0.0, 0.0, 0.0])
    if isinstance(raw_origin, (list, tuple)) and len(raw_origin) >= 3:
        origin = (float(raw_origin[0]), float(raw_origin[1]), float(raw_origin[2]))
    else:
        origin = (0.0, 0.0, 0.0)

    model = BuildingModel(name=proj_name, units=units, origin=origin)
    scale = model.unit_scale
    ox, oy, oz = origin

    # Read storeys / levels
    storeys_data = bldg_info.get("storeys") or manifest_data.get("storeys") or []

    if not storeys_data and ("slabs" in manifest_data or "walls" in manifest_data or "columns" in manifest_data or "beams" in manifest_data):
        # Top-level entities fallback storey
        storeys_data = [{
            "id": "DEFAULT_STOREY",
            "name": "Default Level",
            "elevation": 0.0,
            "height": 3.0,
            "slabs": manifest_data.get("slabs", []),
            "walls": manifest_data.get("walls", []),
            "columns": manifest_data.get("columns", []),
            "beams": manifest_data.get("beams", []),
        }]

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

        # 1. Build Slabs (S-SLAB tag)
        slabs_data = st.get("slabs") or []
        for s_idx, sl in enumerate(slabs_data):
            slab_obj = _build_slab(sl, s_idx, st_elev, scale, ox, oy)
            storey_group.add_child(slab_obj)

        # 2. Build Walls (A-WALL tag)
        walls_data = st.get("walls") or []
        for w_idx, wl in enumerate(walls_data):
            wall_obj = _build_wall(wl, w_idx, st_elev, st_height, scale, ox, oy)
            storey_group.add_child(wall_obj)

        # 3. Build Columns (S-COLS tag)
        cols_data = st.get("columns") or []
        for c_idx, cl in enumerate(cols_data):
            col_obj = _build_column(cl, c_idx, st_elev, st_height, scale, ox, oy)
            storey_group.add_child(col_obj)

        # 4. Build Beams (S-BEAM tag)
        beams_data = st.get("beams") or []
        for b_idx, bm in enumerate(beams_data):
            beam_obj = _build_beam(bm, b_idx, st_elev, scale, ox, oy)
            storey_group.add_child(beam_obj)

        model.storeys.append(storey_group)
        model.root_group.add_child(storey_group)

    return model


def _build_slab(
    sl: Dict[str, Any], idx: int, storey_elevation: float, scale: float, ox: float, oy: float
) -> Slab:
    s_id = str(sl.get("id", f"SLAB_{idx+1}"))
    s_name = str(sl.get("name", f"Slab {idx+1}"))
    tag = str(sl.get("tag", "S-SLAB"))
    thickness = float(sl.get("thickness", 0.2)) * scale
    local_offset = float(sl.get("offset", sl.get("elevation", 0.0))) * scale
    abs_elevation = storey_elevation + local_offset

    raw_boundary = sl.get("boundary") or sl.get("polygon") or sl.get("points") or []
    boundary: List[Tuple[float, float]] = []
    for pt in raw_boundary:
        if isinstance(pt, (list, tuple)) and len(pt) >= 2:
            boundary.append((float(pt[0]) * scale + ox, float(pt[1]) * scale + oy))

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
) -> Wall:
    w_id = str(wl.get("id", f"WALL_{idx+1}"))
    w_name = str(wl.get("name", f"Wall {idx+1}"))
    tag = str(wl.get("tag", "A-WALL"))
    thickness = float(wl.get("thickness", 0.2)) * scale
    height = float(wl.get("height", default_height / scale)) * scale
    local_offset = float(wl.get("offset", wl.get("elevation", 0.0))) * scale
    abs_elevation = storey_elevation + local_offset

    raw_start = wl.get("start", [0.0, 0.0])
    raw_end = wl.get("end", [1.0, 0.0])
    start = (float(raw_start[0]) * scale + ox, float(raw_start[1]) * scale + oy)
    end = (float(raw_end[0]) * scale + ox, float(raw_end[1]) * scale + oy)

    # Openings
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
) -> Column:
    c_id = str(cl.get("id", f"COL_{idx+1}"))
    c_name = str(cl.get("name", f"Column {idx+1}"))
    tag = str(cl.get("tag", "S-COLS"))
    height = float(cl.get("height", default_height / scale)) * scale
    local_offset = float(cl.get("offset", cl.get("elevation", 0.0))) * scale
    abs_elevation = storey_elevation + local_offset

    raw_pos = cl.get("position", cl.get("location", [0.0, 0.0]))
    position = (float(raw_pos[0]) * scale + ox, float(raw_pos[1]) * scale + oy)

    raw_sec = cl.get("section", [0.3, 0.3])
    if isinstance(raw_sec, (list, tuple)) and len(raw_sec) >= 2:
        section = (float(raw_sec[0]) * scale, float(raw_sec[1]) * scale)
    elif isinstance(raw_sec, (int, float)):
        section = (float(raw_sec) * scale, float(raw_sec) * scale)
    else:
        section = (0.3 * scale, 0.3 * scale)

    radius = float(cl["radius"]) * scale if "radius" in cl and cl["radius"] is not None else None
    profile = str(cl.get("profile", "circular" if radius is not None else "rectangular"))
    component = str(cl.get("component", cl.get("type", "ColumnComponent")))

    return Column(
        id_str=c_id,
        name=c_name,
        tag=tag,
        position=position,
        section=section,
        radius=radius,
        height=height,
        elevation=abs_elevation,
        profile=profile,
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
) -> Beam:
    b_id = str(bm.get("id", f"BEAM_{idx+1}"))
    b_name = str(bm.get("name", f"Beam {idx+1}"))
    tag = str(bm.get("tag", "S-BEAM"))

    sec = bm.get("section")
    if isinstance(sec, (list, tuple)) and len(sec) >= 2:
        width = float(sec[0]) * scale
        depth = float(sec[1]) * scale
    else:
        width = float(bm.get("width", bm.get("b", 0.2))) * scale
        depth = float(bm.get("depth", bm.get("height", bm.get("h", 0.4)))) * scale

    local_offset = float(bm.get("offset", bm.get("elevation", 0.0))) * scale
    abs_elevation = storey_elevation + local_offset

    raw_start = bm.get("start", [0.0, 0.0])
    raw_end = bm.get("end", [1.0, 0.0])
    start = (float(raw_start[0]) * scale + ox, float(raw_start[1]) * scale + oy)
    end = (float(raw_end[0]) * scale + ox, float(raw_end[1]) * scale + oy)

    # Preserve rebar and structural properties
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

