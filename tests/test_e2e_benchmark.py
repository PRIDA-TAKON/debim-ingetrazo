"""
E2E Benchmark Validation tests for iconic debim models (Modern Thai House & Church of the Light).
"""

import math
from pathlib import Path
import pytest

from debim_ingetrazo.parser import parse_debim
from debim_ingetrazo.builder import build_geometry, Slab, Wall, Column, Beam, Footing, Group
from debim_ingetrazo.plugin import DebimPlugin

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"
EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"


def test_e2e_modern_thai_house_benchmark():
    file_path = SAMPLES_DIR / "modern_thai_house.debim"
    data = parse_debim(str(file_path))
    model = build_geometry(data)

    assert model.name == "Modern Thai House"
    assert model.units == "m"
    assert model.unit_scale == 1.0
    assert len(model.storeys) == 2

    # 1. Ground Floor (Open Stilt Platform)
    gf = model.storeys[0]
    assert gf.id == "GROUND_FLOOR"
    assert gf.tag == "A-STOREY"
    assert gf.elevation == 0.0
    assert gf.height == 3.2

    # Slab check
    gf_slabs = [c for c in gf.children if isinstance(c, Slab)]
    assert len(gf_slabs) == 1
    slab_stilt = gf_slabs[0]
    assert slab_stilt.id == "SLAB_STILT"
    assert slab_stilt.tag == "S-SLAB"
    assert slab_stilt.area == pytest.approx(96.0)  # 12 x 8
    assert slab_stilt.thickness == 0.25
    assert slab_stilt.volume == pytest.approx(24.0)

    # Core wall check with door opening
    gf_walls = [c for c in gf.children if isinstance(c, Wall)]
    assert len(gf_walls) == 1
    wall_core = gf_walls[0]
    assert wall_core.id == "WALL_CORE_NORTH"
    assert wall_core.tag == "A-WALL"
    assert wall_core.length == pytest.approx(4.0)
    assert wall_core.gross_volume == pytest.approx(4.0 * 0.2 * 3.2)  # 2.56
    assert len(wall_core.openings) == 1
    assert wall_core.openings[0].id == "DOOR_CORE"
    # Net volume = gross - (0.9 * 2.1 * 0.2) = 2.56 - 0.378 = 2.182
    assert wall_core.net_volume == pytest.approx(2.56 - (0.9 * 2.1 * 0.2))

    # Stilt columns
    gf_cols = [c for c in gf.children if isinstance(c, Column)]
    assert len(gf_cols) == 4
    for col in gf_cols:
        assert col.tag == "S-COLS"
        assert col.section == (0.35, 0.35)
        assert col.volume == pytest.approx(0.35 * 0.35 * 3.2)

    # 2. First Floor (Upper Living Level)
    ff = model.storeys[1]
    assert ff.id == "FIRST_FLOOR"
    assert ff.elevation == 3.2
    assert ff.height == 3.0

    ff_walls = [c for c in ff.children if isinstance(c, Wall)]
    assert len(ff_walls) == 2
    wall_south = next(w for w in ff_walls if w.id == "WALL_LIVING_SOUTH")
    assert wall_south.length == pytest.approx(12.0)
    assert len(wall_south.openings) == 1
    assert wall_south.openings[0].id == "WIN_PANORAMA"

    ff_cols = [c for c in ff.children if isinstance(c, Column)]
    assert len(ff_cols) == 1
    col_veranda = ff_cols[0]
    assert col_veranda.profile == "circular"
    assert col_veranda.radius == 0.15
    assert col_veranda.volume == pytest.approx(math.pi * (0.15 ** 2) * 3.0)


def test_e2e_church_of_the_light_benchmark():
    file_path = SAMPLES_DIR / "church_of_the_light.debim"
    data = parse_debim(str(file_path))
    model = build_geometry(data)

    assert model.name == "Church of the Light"
    assert len(model.storeys) == 1

    chapel = model.storeys[0]
    assert chapel.id == "CHAPEL_MAIN"
    assert chapel.tag == "A-STOREY"
    assert chapel.elevation == 0.0
    assert chapel.height == 5.8

    # Slab check
    slabs = [c for c in chapel.children if isinstance(c, Slab)]
    assert len(slabs) == 1
    assert slabs[0].id == "SLAB_CHAPEL_FLOOR"
    assert slabs[0].area == pytest.approx(108.0)  # 6.0 x 18.0

    # Altar wall with cruciform light void openings
    walls = [c for c in chapel.children if isinstance(c, Wall)]
    assert len(walls) == 2
    altar_wall = next(w for w in walls if w.id == "WALL_CROSS_ALTAR")
    assert altar_wall.length == pytest.approx(6.0)
    assert altar_wall.thickness == 0.35
    assert len(altar_wall.openings) == 2

    horiz_void = next(op for op in altar_wall.openings if op.id == "VOID_CROSS_HORIZ")
    vert_void = next(op for op in altar_wall.openings if op.id == "VOID_CROSS_VERT")
    assert horiz_void.width == 5.0 and horiz_void.height == 0.4
    assert vert_void.width == 0.4 and vert_void.height == 4.5

    # Diagonal entry concrete wall
    diag_wall = next(w for w in walls if w.id == "WALL_DIAGONAL_ENTRY")
    # length from (-1.5, 3.0) to (4.5, 12.0) = sqrt(6^2 + 9^2) = sqrt(36 + 81) = sqrt(117) ~= 10.81665
    expected_len = math.hypot(6.0, 9.0)
    assert diag_wall.length == pytest.approx(expected_len)


def test_e2e_playground_benchmark():
    file_path = EXAMPLES_DIR / "playground.debim.yaml"
    data = parse_debim(str(file_path))
    model = build_geometry(data)

    assert model.name == "ทดสอบพิมพ์แบบบ้าน Playground"
    assert model.units == "m" or isinstance(model.units, dict)
    assert model.unit_scale == 1.0
    assert len(model.storeys) == 1

    st = model.storeys[0]
    assert st.id == "L1"
    assert st.elevation == 0.0
    assert st.height == 3.5

    # Grid system check
    assert model.grid_system is not None
    assert model.grid_system.axes_x == {"1": 0.0, "2": 4.0, "3": 8.0}
    assert model.grid_system.axes_y == {"A": 0.0, "B": 5.0}

    # Column check and QTO take-off calculation
    cols = [c for c in st.children if isinstance(c, Column)]
    assert len(cols) == 1
    col = cols[0]
    assert col.tag == "C1"
    assert col.position == (0.0, 0.0)
    assert col.section == (0.3, 0.3)
    assert col.height == 3.5
    assert col.volume == pytest.approx(0.3 * 0.3 * 3.5)  # 0.315 m³


def test_e2e_villa_db1_benchmark():
    file_path = EXAMPLES_DIR / "villa_db1.debim.yaml"
    data = parse_debim(str(file_path))
    model = build_geometry(data)

    assert model.name == "Villa with Spread Footings & DB1 Beams"
    assert model.units == "m"
    assert len(model.storeys) == 1

    st = model.storeys[0]
    assert st.id == "ST_01"
    assert st.elevation == 0.0
    assert st.height == 3.2

    # Total element count in storey
    assert len(st.children) == 17

    # 1. Ground Slab QTO Take-Off Validation
    slabs = [c for c in st.children if isinstance(c, Slab)]
    assert len(slabs) == 1
    slab_gf = slabs[0]
    assert slab_gf.id == "SLAB_GF"
    assert slab_gf.tag == "S-SLAB"
    assert slab_gf.thickness == 0.25
    assert slab_gf.elevation == 0.0
    assert slab_gf.area == pytest.approx(80.0)  # 10m x 8m
    assert slab_gf.volume == pytest.approx(20.0)  # 80m² x 0.25m

    # 2. Spread Footings QTO Take-Off Validation
    footings = [c for c in st.children if isinstance(c, Footing)]
    assert len(footings) == 4
    total_footing_vol = sum(f.volume for f in footings)
    assert total_footing_vol == pytest.approx(1.2)  # 4 x (1m x 1m x 0.3m)
    for f in footings:
        assert f.tag == "S-FOOTING"
        assert f.thickness == 0.3
        assert f.elevation == -0.7
        assert f.section == (1.0, 1.0)
        assert f.volume == pytest.approx(0.3)

    footing_positions = {f.id: f.position for f in footings}
    assert footing_positions["F1_C1"] == pytest.approx((0.0, 0.0))
    assert footing_positions["F2_C2"] == pytest.approx((10.0, 0.0))
    assert footing_positions["F3_C3"] == pytest.approx((10.0, 8.0))
    assert footing_positions["F4_C4"] == pytest.approx((0.0, 8.0))

    # 3. Structural RC Columns QTO Take-Off Validation
    columns = [c for c in st.children if isinstance(c, Column)]
    assert len(columns) == 4
    total_column_vol = sum(c.volume for c in columns)
    assert total_column_vol == pytest.approx(2.048)  # 4 x (0.4m x 0.4m x 3.2m)
    for col in columns:
        assert col.tag == "S-COLS"
        assert col.section == (0.4, 0.4)
        assert col.height == 3.2
        assert col.volume == pytest.approx(0.512)

    col_positions = {c.id: c.position for c in columns}
    assert col_positions["C1"] == pytest.approx((0.0, 0.0))
    assert col_positions["C2"] == pytest.approx((10.0, 0.0))
    assert col_positions["C3"] == pytest.approx((10.0, 8.0))
    assert col_positions["C4"] == pytest.approx((0.0, 8.0))

    # 4. DB1 Reinforced Concrete Beams QTO Take-Off Validation
    beams = [c for c in st.children if isinstance(c, Beam)]
    assert len(beams) == 4
    total_beam_vol = sum(b.volume for b in beams)
    assert total_beam_vol == pytest.approx(2.88)  # 2 x (10m x 0.2m x 0.4m) + 2 x (8m x 0.2m x 0.4m) = 1.6 + 1.28 = 2.88
    for b in beams:
        assert b.tag == "S-BEAM"
        assert b.width == 0.2
        assert b.depth == 0.4
        assert b.elevation == -0.4
        assert b.properties.get("rebar_main") == "4DB12"
        assert b.properties.get("rebar_stirrup") == "RB9@0.15"

    beam_lens = {b.id: b.length for b in beams}
    assert beam_lens["DB1_C1_C2"] == pytest.approx(10.0)
    assert beam_lens["DB1_C2_C3"] == pytest.approx(8.0)
    assert beam_lens["DB1_C3_C4"] == pytest.approx(10.0)
    assert beam_lens["DB1_C4_C1"] == pytest.approx(8.0)

    # 5. Exterior Walls QTO Take-Off Validation
    walls = [c for c in st.children if isinstance(c, Wall)]
    assert len(walls) == 4
    total_wall_gross_vol = sum(w.gross_volume for w in walls)
    assert total_wall_gross_vol == pytest.approx(23.04)  # 2 x (10m x 0.2m x 3.2m) + 2 x (8m x 0.2m x 3.2m) = 12.8 + 10.24 = 23.04
    for w in walls:
        assert w.tag == "A-WALL"
        assert w.thickness == 0.2
        assert w.height == 3.2


def test_plugin_import_benchmark_manifests():
    plugin = DebimPlugin()

    # Import Modern Thai House
    thai_path = SAMPLES_DIR / "modern_thai_house.debim"
    res_thai = plugin.import_manifest(str(thai_path))
    assert res_thai is not None
    assert plugin.active_model is not None
    assert plugin.active_model.name == "Modern Thai House"
    assert len(plugin.active_model.storeys) == 2

    # Import Church of the Light
    church_path = SAMPLES_DIR / "church_of_the_light.debim"
    res_church = plugin.import_manifest(str(church_path))
    assert res_church is not None
    assert plugin.active_model is not None
    assert plugin.active_model.name == "Church of the Light"
    assert len(plugin.active_model.storeys) == 1

    # Import Playground model
    playground_path = EXAMPLES_DIR / "playground.debim.yaml"
    res_playground = plugin.import_manifest(str(playground_path))
    assert res_playground is not None
    assert plugin.active_model is not None
    assert plugin.active_model.name == "ทดสอบพิมพ์แบบบ้าน Playground"
    assert len(plugin.active_model.storeys) == 1

    # Import Villa DB1 model
    villa_path = EXAMPLES_DIR / "villa_db1.debim.yaml"
    res_villa = plugin.import_manifest(str(villa_path))
    assert res_villa is not None
    assert plugin.active_model is not None
    assert plugin.active_model.name == "Villa with Spread Footings & DB1 Beams"
    assert len(plugin.active_model.storeys) == 1
