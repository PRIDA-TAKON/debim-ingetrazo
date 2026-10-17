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
