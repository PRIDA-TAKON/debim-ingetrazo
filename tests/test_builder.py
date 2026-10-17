"""
Unit tests for 3D entity geometry builder (debim_ingetrazo/builder.py).
"""

import math
import pytest
from debim_ingetrazo.parser import parse_debim_str
from debim_ingetrazo.builder import (
    build_geometry, Slab, Wall, Column, Beam, Footing, Roof, Group,
    Stair, Space, Door, Window
)


def test_builder_storeys_and_tags():
    manifest_yaml = """
    project:
      name: Tag & Geometry Test
      units: m
    building:
      storeys:
        - id: GROUND_FLOOR
          name: Level 0
          elevation: 0.0
          height: 3.0
          slabs:
            - id: SLAB_GF
              thickness: 0.2
              boundary: [[0, 0], [10, 0], [10, 5], [0, 5]]
          walls:
            - id: WALL_EXT
              start: [0, 0]
              end: [10, 0]
              thickness: 0.3
              height: 3.0
              openings:
                - id: WIN_1
                  offset: 3.0
                  width: 2.0
                  height: 1.5
          columns:
            - id: COL_RECT
              position: [2.0, 2.0]
              section: [0.4, 0.4]
              height: 3.0
            - id: COL_CIRC
              position: [5.0, 2.0]
              radius: 0.25
              height: 3.0
    """
    data = parse_debim_str(manifest_yaml)
    model = build_geometry(data)

    assert model.name == "Tag & Geometry Test"
    assert model.unit_scale == 1.0
    assert len(model.storeys) == 1

    storey = model.storeys[0]
    assert storey.id == "GROUND_FLOOR"
    assert storey.tag == "A-STOREY"
    assert len(storey.children) == 4

    # 1. Slab tag & calculations
    slab = next(c for c in storey.children if isinstance(c, Slab))
    assert slab.id == "SLAB_GF"
    assert slab.tag == "S-SLAB"
    assert slab.area == 50.0  # 10 * 5
    assert slab.thickness == 0.2
    assert slab.volume == pytest.approx(10.0)
    bounds = slab.get_3d_bounds()
    assert bounds == ((0.0, 0.0, 0.0), (10.0, 5.0, 0.2))

    # 2. Wall tag & openings
    wall = next(c for c in storey.children if isinstance(c, Wall))
    assert wall.id == "WALL_EXT"
    assert wall.tag == "A-WALL"
    assert wall.length == 10.0
    assert wall.gross_volume == pytest.approx(10.0 * 0.3 * 3.0)  # 9.0
    # Net volume = gross - (win_w * win_h * thickness) = 9.0 - (2.0 * 1.5 * 0.3) = 9.0 - 0.9 = 8.1
    assert wall.net_volume == pytest.approx(8.1)
    assert len(wall.openings) == 1
    assert wall.openings[0].id == "WIN_1"

    # 3. Columns tag & reusable component instances
    rect_col = next(c for c in storey.children if isinstance(c, Column) and c.id == "COL_RECT")
    assert rect_col.tag == "S-COLS"
    assert rect_col.volume == pytest.approx(0.4 * 0.4 * 3.0)

    circ_col = next(c for c in storey.children if isinstance(c, Column) and c.id == "COL_CIRC")
    assert circ_col.tag == "S-COLS"
    assert circ_col.volume == pytest.approx(math.pi * (0.25 ** 2) * 3.0)


def test_builder_unit_scaling_and_offsets():
    manifest_yaml = """
    project:
      name: Millimeter Project
      units: mm
      origin: [1000, 2000, 500]
    building:
      storeys:
        - id: L1
          elevation: 0
          height: 3000
          slabs:
            - id: SLAB_MM
              thickness: 200
              elevation: 0
              boundary: [[0, 0], [2000, 0], [2000, 2000], [0, 2000]]
    """
    data = parse_debim_str(manifest_yaml)
    model = build_geometry(data)

    assert model.unit_scale == 0.001
    assert model.origin == (1000.0, 2000.0, 500.0)

    storey = model.storeys[0]
    assert storey.elevation == 500.0  # oz = 500
    assert storey.height == 3.0  # 3000 mm = 3.0 m

    slab = storey.children[0]
    assert isinstance(slab, Slab)
    assert slab.thickness == 0.2
    assert slab.elevation == 500.0
    # Boundary scaled + ox, oy
    assert slab.boundary == [(1000.0, 2000.0), (1002.0, 2000.0), (1002.0, 2002.0), (1000.0, 2002.0)]
    assert slab.area == pytest.approx(4.0)  # 2m x 2m


def test_builder_beams():
    manifest_yaml = """
    project:
      name: RC Beam Test
      units: m
    storeys:
      - id: GF
        name: Ground Floor
        elevation: 0.0
        height: 3.2
        beams:
          - id: DB1_1
            name: "Ground Beam DB1"
            tag: "S-BEAM"
            section: [0.2, 0.4]
            start: [0, 0]
            end: [10, 0]
            elevation: -0.4
            rebar: "4db12 rb9@0.15"
            rebar_main: "4DB12"
            rebar_stirrup: "RB9@0.15"
    """
    data = parse_debim_str(manifest_yaml)
    model = build_geometry(data)

    storey = model.storeys[0]
    assert len(storey.children) == 1
    beam = storey.children[0]
    assert isinstance(beam, Beam)
    assert beam.id == "DB1_1"
    assert beam.tag == "S-BEAM"
    assert beam.width == 0.2
    assert beam.depth == 0.4
    assert beam.length == 10.0
    assert beam.volume == pytest.approx(10.0 * 0.2 * 0.4)
    assert beam.elevation == -0.4
    assert beam.properties["rebar"] == "4db12 rb9@0.15"
    assert beam.properties["rebar_main"] == "4DB12"
    assert beam.properties["rebar_stirrup"] == "RB9@0.15"


def test_builder_playground_debim_yaml():
    from pathlib import Path
    from debim_ingetrazo.parser import parse_debim
    playground_path = Path(__file__).resolve().parent.parent / "examples" / "playground.debim.yaml"
    data = parse_debim(playground_path)
    model = build_geometry(data)

    assert model.name == "ทดสอบพิมพ์แบบบ้าน Playground"
    assert model.unit_scale == 1.0
    assert len(model.storeys) == 1

    storey = model.storeys[0]
    assert storey.id == "L1"
    assert storey.elevation == 0.0
    assert storey.height == 3.5

    assert len(storey.children) == 1
    col = storey.children[0]
    assert isinstance(col, Column)
    assert col.tag == "C1"
    assert col.position == (0.0, 0.0)
    assert col.section == (0.3, 0.3)
    assert col.height == 3.5


def test_parametric_grid_resolver_and_arithmetic_expressions():
    from debim_ingetrazo.builder import GridSystem

    grids_data = {
        "axes_x": {"1": 0.0, "2": 4.0, "3": 8.0},
        "axes_y": {"A": 0.0, "B": 5.0},
    }
    gs = GridSystem(grids_data)

    # Intersection resolution
    assert gs.resolve_point(["1", "A"]) == (0.0, 0.0)
    assert gs.resolve_point(["2", "B"]) == (4.0, 5.0)

    # Linear resolution
    p1, p2 = gs.resolve_line(["1", "A"], ["2", "A"])
    assert p1 == (0.0, 0.0)
    assert p2 == (4.0, 0.0)

    # Arithmetic offset expression evaluation
    assert gs.resolve_point(["GX_1 + 0.10", "GY_1 - 0.10"]) == (0.10, -0.10)
    assert gs.resolve_point(["GX_2 - 0.20", "GY_B + 0.50"]) == (3.80, 5.50)


def test_dual_mode_ifc_elements_and_grid_faces():
    manifest_yaml = """
    schema: "IFC4-Minimal"
    project:
      name: "Dual Mode IFC Test"
      units:
        length: "METER"

    spatial_structure:
      storeys:
        - id: "ST_01"
          name: "Ground Level"
          elevation: 0.0
          height: 3.2

    grids:
      axes_x:
        "1": 0.0
        "2": 6.0
      axes_y:
        "A": 0.0
        "B": 4.0

    elements:
      - class: IfcColumn
        tag: "C1"
        profile:
          shape: BOX
          width: 0.4
          depth: 0.4
        placement:
          grid: ["1", "A"]
          storey: "ST_01"

      - class: IfcWall
        tag: "W1"
        thickness: 0.2
        placement:
          from_grid: ["1", "A"]
          to_grid: ["2", "A"]
          storey: "ST_01"

      - class: IfcSlab
        tag: "SL1"
        thickness: 0.25
        placement:
          from_grid: ["1", "A"]
          to_grid: ["2", "B"]
          storey: "ST_01"

      - class: IfcBeam
        tag: "B1"
        profile:
          shape: BOX
          width: 0.25
          depth: 0.50
        placement:
          from_grid: ["1", "B"]
          to_grid: ["2", "B"]
          storey: "ST_01"
    """
    data = parse_debim_str(manifest_yaml)
    model = build_geometry(data)

    assert len(model.storeys) == 1
    st = model.storeys[0]
    assert len(st.children) == 4

    col = next(c for c in st.children if isinstance(c, Column))
    assert col.position == (0.0, 0.0)
    assert col.section == (0.4, 0.4)

    wall = next(c for c in st.children if isinstance(c, Wall))
    assert wall.start == (0.0, 0.0)
    assert wall.end == (6.0, 0.0)

    slab = next(c for c in st.children if isinstance(c, Slab))
    assert slab.boundary == [(0.0, 0.0), (6.0, 0.0), (6.0, 4.0), (0.0, 4.0)]

    beam = next(c for c in st.children if isinstance(c, Beam))
    assert beam.start == (0.0, 4.0)
    assert beam.end == (6.0, 4.0)
    assert beam.width == 0.25
    assert beam.depth == 0.50

    # Grid faces rendering test
    from debim_ingetrazo.plugin import DebimPlugin
    grid_faces = DebimPlugin._build_grid_faces(model.grid_system)
    # 4 grid lines * (1 line ribbon + 2 balloons) = 12 faces
    assert len(grid_faces) == 12


def test_footing_object_and_auto_placement():
    # 1. Direct Footing class unit test
    f_unit = Footing(
        id_str="F1",
        name="Isolated Footing F1",
        tag="S-FOOTING",
        position=(2.0, 3.0),
        section=(1.2, 1.2),
        thickness=0.5,
        elevation=-0.5,
        footing_type="isolated",
        column_id="C1",
    )
    assert f_unit.id == "F1"
    assert f_unit.tag == "S-FOOTING"
    assert f_unit.volume == pytest.approx(1.2 * 1.2 * 0.5)
    bounds = f_unit.get_3d_bounds()
    assert bounds == ((1.4, 2.4, -0.5), (2.6, 3.6, 0.0))
    d_info = f_unit.to_dict()
    assert d_info["type"] == "Footing"
    assert d_info["footing_type"] == "isolated"
    assert d_info["column_id"] == "C1"

    # 2. Manifest parsing & Column auto-placement
    manifest_yaml = """
    project:
      name: Footing Test Project
      units: m
    storeys:
      - id: GF
        elevation: 0.0
        columns:
          - id: C1
            position: [4.0, 5.0]
            section: [0.3, 0.3]
            height: 3.0
            elevation: 0.0
        footings:
          - id: F_AUTO
            column: "C1"
            section: [1.5, 1.5]
            thickness: 0.6
          - id: F_PILE
            tag: "S-FOOTING"
            type: "pile_cap"
            section: [2.0, 2.0]
            thickness: 0.8
            position: [10.0, 10.0]
            elevation: -1.0
    """
    data = parse_debim_str(manifest_yaml)
    model = build_geometry(data)

    st = model.storeys[0]
    footings = [c for c in st.children if isinstance(c, Footing)]
    assert len(footings) == 2

    # Auto-placed footing under column C1
    f_auto = next(f for f in footings if f.id == "F_AUTO")
    assert f_auto.position == (4.0, 5.0)
    assert f_auto.thickness == 0.6
    # Auto elevation = col.elevation - thickness = 0.0 - 0.6 = -0.6
    assert f_auto.elevation == pytest.approx(-0.6)
    assert f_auto.column_id == "C1"

    # Explicit pile cap footing
    f_pile = next(f for f in footings if f.id == "F_PILE")
    assert f_pile.footing_type == "pile_cap"
    assert f_pile.position == (10.0, 10.0)
    assert f_pile.elevation == -1.0


def test_roof_object_types_and_geometry():
    # 1. Direct Roof class unit test
    roof_gable = Roof(
        id_str="RF_GABLE",
        name="Main Roof Gable",
        boundary=[(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)],
        roof_type="gable",
        pitch=30.0,
        overhang=0.5,
        thickness=0.2,
        elevation=6.0,
        ridge_direction="X",
    )
    assert roof_gable.roof_type == "gable"
    assert roof_gable.overhang == 0.5
    # eaves_boundary expanded by 0.5m on all sides: [-0.5, 10.5] x [-0.5, 8.5]
    eb = roof_gable.eaves_boundary
    assert eb == [(-0.5, -0.5), (10.5, -0.5), (10.5, 8.5), (-0.5, 8.5)]
    # Eaves width = 11.0, depth = 9.0 -> area = 99.0
    assert roof_gable.area == pytest.approx(99.0)
    assert roof_gable.volume == pytest.approx(99.0 * 0.2)
    # Bounds: ridge height above eaves = (9.0 / 2) * tan(30deg) = 4.5 * 0.57735 = ~2.598m
    bounds = roof_gable.get_3d_bounds()
    assert bounds[0] == (-0.5, -0.5, 6.0)
    assert bounds[1][2] == pytest.approx(6.0 + 4.5 * math.tan(math.radians(30.0)) + 0.2)

    # 2. Manifest parsing for all 4 roof types: Gable, Hip, Shed, Flat
    manifest_yaml = """
    schema: "IFC4-Minimal"
    project:
      name: "Roof Types Test"
    spatial_structure:
      storeys:
        - id: "ROOF_LEVEL"
          elevation: 6.0
    elements:
      - class: IfcRoof
        id: "RF_1"
        type: "gable"
        pitch: 30
        eaves: 0.6
        ridge_direction: "X"
        boundary: [[0, 0], [12, 0], [12, 8], [0, 8]]
        placement:
          storey: "ROOF_LEVEL"

      - class: IfcRoof
        id: "RF_2"
        type: "hip"
        pitch: 25
        eaves: 0.5
        boundary: [[0, 0], [10, 0], [10, 6], [0, 6]]
        placement:
          storey: "ROOF_LEVEL"

      - class: IfcRoof
        id: "RF_3"
        type: "shed"
        pitch: 15
        eaves: 0.4
        ridge_direction: "Y"
        boundary: [[0, 0], [8, 0], [8, 5], [0, 5]]
        placement:
          storey: "ROOF_LEVEL"

      - class: IfcRoof
        id: "RF_4"
        type: "flat"
        pitch: 0
        eaves: 0.2
        boundary: [[0, 0], [6, 0], [6, 6], [0, 6]]
        placement:
          storey: "ROOF_LEVEL"
    """
    data = parse_debim_str(manifest_yaml)
    model = build_geometry(data)

    st = model.storeys[0]
    roofs = [c for c in st.children if isinstance(c, Roof)]
    assert len(roofs) == 4

    rf1 = next(r for r in roofs if r.id == "RF_1")
    assert rf1.roof_type == "gable"
    assert rf1.pitch == 30.0
    assert rf1.overhang == 0.6

    rf2 = next(r for r in roofs if r.id == "RF_2")
    assert rf2.roof_type == "hip"
    assert rf2.pitch == 25.0

    rf3 = next(r for r in roofs if r.id == "RF_3")
    assert rf3.roof_type == "shed"
    assert rf3.pitch == 15.0

    rf4 = next(r for r in roofs if r.id == "RF_4")
    assert rf4.roof_type == "flat"
    assert rf4.pitch == 0.0


def test_stair_geometry_and_steps():
    stair = Stair(
        id_str="STAIR_01",
        name="Main Staircase",
        tag="A-STAIR",
        start=(0.0, 0.0),
        end=(4.0, 0.0),
        width=1.2,
        height=3.2,
        num_steps=16,
        landing_depth=0.8,
        landing_thickness=0.15,
        elevation=0.0,
        stair_type="straight",
    )
    assert stair.id == "STAIR_01"
    assert stair.tag == "A-STAIR"
    assert stair.width == 1.2
    assert stair.height == 3.2
    assert stair.num_steps == 16
    assert stair.riser_height == pytest.approx(0.2)  # 3.2 / 16
    assert stair.total_run == pytest.approx(4.0)
    # run for steps = 4.0 - 0.8 = 3.2 -> tread_depth = 3.2 / 16 = 0.2
    assert stair.tread_depth == pytest.approx(0.2)
    assert stair.volume > 0.0
    bounds = stair.get_3d_bounds()
    assert bounds[0] == (0.0, -0.6, 0.0)
    assert bounds[1] == (4.0, 0.6, 3.2)
    d = stair.to_dict()
    assert d["type"] == "Stair"
    assert d["num_steps"] == 16
    assert d["riser_height"] == pytest.approx(0.2)


def test_space_geometry_and_zone_calculations():
    # 5m x 4m room -> area = 20 m², height = 3m -> volume = 60 m³
    space = Space(
        id_str="RM_101",
        name="Living Room",
        tag="A-SPACE",
        boundary=[(0.0, 0.0), (5.0, 0.0), (5.0, 4.0), (0.0, 4.0)],
        height=3.0,
        elevation=0.0,
        number="101",
        zone="Living",
    )
    assert space.id == "RM_101"
    assert space.tag == "A-SPACE"
    assert space.number == "101"
    assert space.zone == "Living"
    assert space.area == pytest.approx(20.0)
    assert space.volume == pytest.approx(60.0)
    bounds = space.get_3d_bounds()
    assert bounds == ((0.0, 0.0, 0.0), (5.0, 4.0, 3.0))
    d = space.to_dict()
    assert d["type"] == "Space"
    assert d["area"] == pytest.approx(20.0)
    assert d["volume"] == pytest.approx(60.0)


def test_door_and_window_geometry_components():
    # 1. Door component with 3D frames and leaf panel
    door = Door(
        id_str="D1",
        name="Main Entrance Door",
        tag="A-DOOR",
        position=(2.0, 0.0),
        width=1.0,
        height=2.2,
        sill_height=0.0,
        depth=0.15,
        frame_width=0.05,
        panel_thickness=0.04,
        elevation=0.0,
        direction=0.0,
        door_type="single",
    )
    assert door.id == "D1"
    assert door.tag == "A-DOOR"
    assert door.width == 1.0
    assert door.height == 2.2
    assert door.volume > 0.0
    bounds_d = door.get_3d_bounds()
    assert bounds_d[0][2] == 0.0
    assert bounds_d[1][2] == 2.2
    dict_d = door.to_dict()
    assert dict_d["type"] == "Door"
    assert dict_d["door_type"] == "single"

    # 2. Window component with 3D frames and glazed glass panel
    window = Window(
        id_str="W1",
        name="Bedroom Window",
        tag="A-WINDOW",
        position=(4.0, 0.0),
        width=1.5,
        height=1.2,
        sill_height=0.9,
        depth=0.10,
        frame_width=0.05,
        glass_thickness=0.01,
        elevation=0.0,
        direction=90.0,
        window_type="casement",
    )
    assert window.id == "W1"
    assert window.tag == "A-WINDOW"
    assert window.width == 1.5
    assert window.height == 1.2
    assert window.sill_height == 0.9
    assert window.volume > 0.0
    bounds_w = window.get_3d_bounds()
    assert bounds_w[0][2] == 0.9
    assert bounds_w[1][2] == 2.1  # sill 0.9 + height 1.2
    dict_w = window.to_dict()
    assert dict_w["type"] == "Window"
    assert dict_w["window_type"] == "casement"


def test_builder_architectural_manifest_parsing():
    manifest_yaml = """
    schema: "IFC4-Minimal"
    project:
      name: "Architectural Components Test"
      units: "m"

    spatial_structure:
      storeys:
        - id: "L1"
          name: "Ground Floor"
          elevation: 0.0
          height: 3.2

    elements:
      - class: IfcStair
        id: "ST_1"
        width: 1.2
        height: 3.2
        steps: 16
        landing: 1.0
        placement:
          from_grid: [0, 0]
          to_grid: [5, 0]
          storey: "L1"

      - class: IfcSpace
        id: "SP_1"
        number: "101"
        zone: "Lounge"
        boundary: [[0, 0], [6, 0], [6, 5], [0, 5]]
        placement:
          storey: "L1"

      - class: IfcDoor
        id: "DR_1"
        width: 0.9
        height: 2.1
        type: "single"
        placement:
          grid: [3, 0]
          storey: "L1"

      - class: IfcWindow
        id: "WN_1"
        width: 1.4
        height: 1.2
        sill: 1.0
        type: "casement"
        placement:
          grid: [4, 5]
          storey: "L1"
    """
    data = parse_debim_str(manifest_yaml)
    model = build_geometry(data)

    assert len(model.storeys) == 1
    st = model.storeys[0]
    assert len(st.children) == 4

    stair = next(c for c in st.children if isinstance(c, Stair))
    assert stair.id == "ST_1"
    assert stair.tag == "A-STAIR"
    assert stair.num_steps == 16
    assert stair.landing_depth == 1.0

    space = next(c for c in st.children if isinstance(c, Space))
    assert space.id == "SP_1"
    assert space.tag == "A-SPACE"
    assert space.number == "101"
    assert space.zone == "Lounge"
    assert space.area == pytest.approx(30.0)  # 6 x 5
    assert space.volume == pytest.approx(30.0 * 3.2)  # 96.0

    door = next(c for c in st.children if isinstance(c, Door))
    assert door.id == "DR_1"
    assert door.tag == "A-DOOR"
    assert door.position == (3.0, 0.0)
    assert door.width == 0.9
    assert door.height == 2.1

    window = next(c for c in st.children if isinstance(c, Window))
    assert window.id == "WN_1"
    assert window.tag == "A-WINDOW"
    assert window.position == (4.0, 5.0)
    assert window.width == 1.4
    assert window.sill_height == 1.0
