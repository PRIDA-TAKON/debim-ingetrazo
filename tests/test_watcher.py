import time
from pathlib import Path
import pytest

from debim_ingetrazo.watcher import DebimWatcher


def test_watcher_file_change_detection(tmp_path: Path):
    target_file = tmp_path / "model.debim"
    target_file.write_text("""
project:
  name: Initial Model
""", encoding="utf-8")

    received_models = []

    def on_changed(path, manifest, model):
        received_models.append(model)

    watcher = DebimWatcher(file_path=target_file, poll_interval=0.1, on_file_changed=on_changed)
    watcher.start()
    assert watcher.is_running

    time.sleep(0.05)

    # Modify file
    target_file.write_text("""
project:
  name: Updated Model
""", encoding="utf-8")

    changed = watcher.check_now()
    assert changed is True
    assert len(received_models) == 1
    assert received_models[0].name == "Updated Model"

    watcher.stop()
    assert not watcher.is_running


def test_watcher_no_change_when_same_content(tmp_path: Path):
    target_file = tmp_path / "model.debim"
    target_file.write_text("project:\n  name: Static Model\n", encoding="utf-8")

    received_models = []
    watcher = DebimWatcher(file_path=target_file, poll_interval=0.1, on_file_changed=lambda p, m, b: received_models.append(b))
    watcher._reset_file_state()

    changed = watcher.check_now()
    assert changed is False
    assert len(received_models) == 0
