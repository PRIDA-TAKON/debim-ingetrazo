"""
E2E Benchmark Validation tests for iconic debim models (Modern Thai House & Church of the Light).
"""

import math
from pathlib import Path
import pytest

from debim_ingetrazo.parser import parse_debim
from debim_ingetrazo.builder import build_geometry, Slab, Wall, Column, Group
from debim_ingetrazo.plugin import DebimPlugin

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"


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
