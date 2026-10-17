"""
Unit tests for 3D entity geometry builder (debim_ingetrazo/builder.py).
"""

import math
import pytest
from debim_ingetrazo.parser import parse_debim_str
from debim_ingetrazo.builder import build_geometry, Slab, Wall, Column, Group


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
