"""
Unit tests for 3D entity geometry builder (debim_ingetrazo/builder.py).
"""

import math
import pytest
from debim_ingetrazo.parser import parse_debim_str
from debim_ingetrazo.builder import build_geometry, Slab, Wall, Column, Beam, Group


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
