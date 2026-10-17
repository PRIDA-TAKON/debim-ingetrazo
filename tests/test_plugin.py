from pathlib import Path
from debim_ingetrazo.plugin import DebimPlugin, register_plugin, Tool


def test_debim_plugin_subclasses_tool():
    plugin = DebimPlugin()
    assert isinstance(plugin, Tool)


def test_debim_plugin_menu_registration():
    plugin = DebimPlugin()
    menu_reg = plugin.get_menu_registration()

    assert menu_reg["menu_path"] == "Extensions > debim"
    items = menu_reg["items"]
    labels = [item["label"] for item in items]

    assert "Import .debim Manifest..." in labels
    assert "Toggle Live Sync" in labels
    assert "Open Agentic AI Console" in labels


def test_debim_plugin_toolbar_registration():
    plugin = DebimPlugin()
    tb_reg = plugin.get_toolbar_registration()

    assert tb_reg["toolbar_name"] == "debim"
    action = tb_reg["action"]
    assert "icon" in action
    icon_path = Path(action["icon"])
    assert icon_path.exists()
    assert icon_path.suffix in (".svg", ".png")


def test_debim_plugin_toggle_live_sync():
    plugin = DebimPlugin()
    assert not plugin.live_sync_enabled

    res1 = plugin.toggle_live_sync()
    assert res1 is True
    assert plugin.live_sync_enabled is True
    assert plugin.agent_bridge.is_running is True

    res2 = plugin.toggle_live_sync()
    assert res2 is False
    assert plugin.live_sync_enabled is False
    assert plugin.agent_bridge.is_running is False


def test_debim_plugin_open_agentic_ai_console():
    plugin = DebimPlugin()
    console = plugin.open_agentic_ai_console()
    assert console.is_open is True

    model = console.execute_live("project:\n  name: AI Generated House\n")
    assert model.name == "AI Generated House"
    assert plugin.active_model.name == "AI Generated House"


def test_register_plugin_with_dummy_app():
    class DummyApp:
        def __init__(self):
            self.tools = []

        def register_tool(self, tool):
            self.tools.append(tool)

    app = DummyApp()
    plugin = register_plugin(app)

    assert isinstance(plugin, DebimPlugin)
    assert len(app.tools) == 1
    assert app.tools[0] == plugin


def test_debim_plugin_build_footing_faces():
    from debim_ingetrazo.builder import Footing

    footing = Footing(
        id_str="F1",
        position=(5.0, 5.0),
        section=(1.2, 1.2),
        thickness=0.5,
        elevation=-0.5,
    )
    faces = DebimPlugin._build_footing_faces(footing)

    # Footing is a box volume -> 6 quad faces
    assert len(faces) == 6
    for face in faces:
        assert len(face) == 4
        for pt in face:
            assert len(pt) == 3


def test_debim_plugin_build_roof_faces():
    from debim_ingetrazo.builder import Roof

    # 1. Gable roof
    roof_gable = Roof(
        id_str="RF_GABLE",
        boundary=[(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)],
        roof_type="gable",
        pitch=30.0,
        overhang=0.5,
        elevation=3.0,
        ridge_direction="X",
    )
    faces_gable = DebimPlugin._build_roof_faces(roof_gable)
    # Gable roof has 2 sloping quads + 2 gable end triangles = 4 faces
    assert len(faces_gable) == 4
    for face in faces_gable:
        assert len(face) in (3, 4)

    # 2. Hip roof
    roof_hip = Roof(
        id_str="RF_HIP",
        boundary=[(0.0, 0.0), (10.0, 0.0), (10.0, 6.0), (0.0, 6.0)],
        roof_type="hip",
        pitch=25.0,
        overhang=0.5,
        elevation=3.0,
    )
    faces_hip = DebimPlugin._build_roof_faces(roof_hip)
    # Hip roof has 4 sloping faces (2 trapezoids + 2 triangles)
    assert len(faces_hip) == 4

    # 3. Shed roof
    roof_shed = Roof(
        id_str="RF_SHED",
        boundary=[(0.0, 0.0), (8.0, 0.0), (8.0, 5.0), (0.0, 5.0)],
        roof_type="shed",
        pitch=15.0,
        overhang=0.4,
        elevation=3.0,
        ridge_direction="X",
    )
    faces_shed = DebimPlugin._build_roof_faces(roof_shed)
    # Shed roof has 1 sloping quad + 2 side triangles + 1 high wall quad = 4 faces
    assert len(faces_shed) == 4

    # 4. Flat roof
    roof_flat = Roof(
        id_str="RF_FLAT",
        boundary=[(0.0, 0.0), (6.0, 0.0), (6.0, 6.0), (0.0, 6.0)],
        roof_type="flat",
        pitch=0.0,
        overhang=0.2,
        thickness=0.2,
        elevation=3.0,
    )
    faces_flat = DebimPlugin._build_roof_faces(roof_flat)
    # Flat roof slab has bottom + top + 4 sides = 6 quad faces
    assert len(faces_flat) == 6


def test_debim_plugin_build_stair_faces():
    from debim_ingetrazo.builder import Stair

    stair = Stair(
        id_str="STAIR_1",
        start=(0.0, 0.0),
        end=(4.0, 0.0),
        width=1.0,
        height=3.0,
        num_steps=10,
        landing_depth=1.0,
        elevation=0.0,
    )
    faces = DebimPlugin._build_stair_faces(stair)

    # 10 steps * 6 faces/box + 1 landing * 6 faces/box = 66 quad faces
    assert len(faces) == 66
    for face in faces:
        assert len(face) == 4
        for pt in face:
            assert len(pt) == 3


def test_debim_plugin_build_space_faces():
    from debim_ingetrazo.builder import Space

    space = Space(
        id_str="ROOM_1",
        boundary=[(0.0, 0.0), (4.0, 0.0), (4.0, 3.0), (0.0, 3.0)],
        height=3.0,
        elevation=0.0,
    )
    faces = DebimPlugin._build_space_faces(space)

    # Rectangular room -> floor + ceiling + 4 side walls = 6 faces
    assert len(faces) == 6
    for face in faces:
        assert len(face) == 4
        for pt in face:
            assert len(pt) == 3


def test_debim_plugin_build_door_and_window_faces():
    from debim_ingetrazo.builder import Door, Window

    # 1. Door faces: top frame, left jamb, right jamb, leaf panel -> 4 box components * 6 faces = 24 faces
    door = Door(
        id_str="D_TEST",
        position=(1.0, 0.0),
        width=0.9,
        height=2.1,
        depth=0.1,
        direction=0.0,
    )
    door_faces = DebimPlugin._build_door_faces(door)
    assert len(door_faces) == 24
    for face in door_faces:
        assert len(face) == 4

    # 2. Window faces: top, bottom, left jamb, right jamb, glass panel -> 5 box components * 6 faces = 30 faces
    window = Window(
        id_str="W_TEST",
        position=(3.0, 0.0),
        width=1.2,
        height=1.5,
        depth=0.1,
        direction=0.0,
    )
    window_faces = DebimPlugin._build_window_faces(window)
    assert len(window_faces) == 30
    for face in window_faces:
        assert len(face) == 4
