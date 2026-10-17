import pytest
from debim_ingetrazo.console import AIConsoleDialog, open_console_dialog


def test_ai_console_dialog_execution():
    events = []

    def on_sub(text, manifest, model):
        events.append((text, model))

    dialog = open_console_dialog(on_submit=on_sub)
    assert dialog.is_open is True

    model = dialog.execute_live("""
project:
  name: Live Console Tower
building:
  storeys:
    - name: Base Level
""")

    assert model.name == "Live Console Tower"
    assert len(events) == 1
    assert events[0][1].name == "Live Console Tower"
    assert dialog.last_model == model

    dialog.close()
    assert dialog.is_open is False
