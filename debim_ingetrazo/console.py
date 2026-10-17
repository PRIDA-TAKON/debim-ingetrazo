"""
Interactive Agentic AI Console Dialog for debim-ingetrazo.
Allows live typing or pasting of .debim manifests to immediately re-render in IngeTrazo viewport.
"""

import logging
from typing import Any, Callable, Dict, Optional

from debim_ingetrazo.builder import BuildingModel, build_geometry
from debim_ingetrazo.parser import parse_debim_str

logger = logging.getLogger("debim_ingetrazo.console")


class AIConsoleDialog:
    """
    Interactive AI Console Dialog abstraction & PySide6 GUI Dialog.
    Supports live text input, parsing, and callback notification to update the active viewport.
    """

    def __init__(
        self,
        on_submit: Optional[Callable[[str, Dict[str, Any], BuildingModel], Any]] = None,
        initial_text: str = "",
        parent: Optional[Any] = None,
    ):
        self.on_submit = on_submit
        self.current_text: str = initial_text
        self.history: list[str] = []
        self.is_open: bool = False
        self.last_model: Optional[BuildingModel] = None
        self.parent = parent
        self._qt_dialog: Optional[Any] = None

    def open(self) -> None:
        """Opens/displays the interactive console dialog."""
        self.is_open = True
        logger.info("Agentic AI Console dialog opened.")
        self._show_qt_dialog()

    def _show_qt_dialog(self) -> None:
        """Instantiates and presents the PySide6 QDialog if available."""
        try:
            from PySide6.QtWidgets import (
                QApplication,
                QDialog,
                QVBoxLayout,
                QHBoxLayout,
                QPlainTextEdit,
                QPushButton,
                QLabel,
            )
            from PySide6.QtGui import QFont

            if QApplication.instance() is None:
                # No QApplication running (e.g. running unit tests headlessly)
                return

            if self._qt_dialog is None:
                dlg = QDialog(self.parent)
                dlg.setWindowTitle("debim: Agentic AI Console")
                dlg.resize(680, 520)

                layout = QVBoxLayout(dlg)

                header = QLabel(
                    "<b>debim Agentic Building-as-Code Console</b><br>"
                    "<span style='color: #666;'>Type or paste your .debim manifest below. "
                    "Click <b>Execute Live</b> to compile directly to 3D geometry in the viewport.</span>"
                )
                header.setWordWrap(True)
                layout.addWidget(header)

                editor = QPlainTextEdit(dlg)
                font = QFont("Consolas", 10)
                font.setStyleHint(QFont.Monospace)
                editor.setFont(font)

                sample_manifest = (
                    "project:\n"
                    "  name: \"AI Generated Villa\"\n"
                    "  units: \"m\"\n"
                    "storeys:\n"
                    "  - id: \"ST_01\"\n"
                    "    name: \"Ground Floor\"\n"
                    "    elevation: 0.0\n"
                    "    height: 3.2\n"
                    "    slabs:\n"
                    "      - id: \"SLAB_GF\"\n"
                    "        thickness: 0.25\n"
                    "        boundary: [[0, 0], [10, 0], [10, 8], [0, 8]]\n"
                    "    columns:\n"
                    "      - id: \"C1\"\n"
                    "        position: [0, 0]\n"
                    "        section: [0.4, 0.4]\n"
                    "        height: 3.2\n"
                    "      - id: \"C2\"\n"
                    "        position: [10, 0]\n"
                    "        section: [0.4, 0.4]\n"
                    "        height: 3.2\n"
                    "      - id: \"C3\"\n"
                    "        position: [10, 8]\n"
                    "        section: [0.4, 0.4]\n"
                    "        height: 3.2\n"
                    "      - id: \"C4\"\n"
                    "        position: [0, 8]\n"
                    "        section: [0.4, 0.4]\n"
                    "        height: 3.2\n"
                    "    walls:\n"
                    "      - id: \"W1\"\n"
                    "        start: [0, 0]\n"
                    "        end: [10, 0]\n"
                    "        thickness: 0.2\n"
                    "        height: 3.2\n"
                    "      - id: \"W2\"\n"
                    "        start: [10, 0]\n"
                    "        end: [10, 8]\n"
                    "        thickness: 0.2\n"
                    "        height: 3.2\n"
                    "      - id: \"W3\"\n"
                    "        start: [10, 8]\n"
                    "        end: [0, 8]\n"
                    "        thickness: 0.2\n"
                    "        height: 3.2\n"
                    "      - id: \"W4\"\n"
                    "        start: [0, 8]\n"
                    "        end: [0, 0]\n"
                    "        thickness: 0.2\n"
                    "        height: 3.2\n"
                )
                editor.setPlainText(self.current_text or sample_manifest)
                layout.addWidget(editor)

                btn_layout = QHBoxLayout()
                status_lbl = QLabel("")
                btn_layout.addWidget(status_lbl)
                btn_layout.addStretch()

                btn_exec = QPushButton("⚡ Execute Live")
                btn_exec.setStyleSheet("background-color: #007ACC; color: white; font-weight: bold; padding: 6px 14px;")

                def on_exec_clicked():
                    content = editor.toPlainText()
                    try:
                        self.execute_live(content)
                        status_lbl.setText("<span style='color: green;'>✓ Live Sync Applied!</span>")
                    except Exception as e:
                        status_lbl.setText(f"<span style='color: red;'>Error: {e}</span>")

                btn_exec.clicked.connect(on_exec_clicked)
                btn_layout.addWidget(btn_exec)

                btn_close = QPushButton("Close")
                btn_close.clicked.connect(dlg.close)
                btn_layout.addWidget(btn_close)

                layout.addLayout(btn_layout)

                dlg.finished.connect(lambda: setattr(self, "is_open", False))
                self._qt_dialog = dlg

            self._qt_dialog.show()
            self._qt_dialog.raise_()
            self._qt_dialog.activateWindow()
        except ImportError:
            # Fallback for headless/test environments
            pass
        except Exception as e:
            logger.warning(f"Failed to show Qt AIConsoleDialog: {e}")

    def close(self) -> None:
        """Closes/hides the console dialog."""
        self.is_open = False
        if self._qt_dialog is not None:
            try:
                self._qt_dialog.close()
            except Exception:
                pass
        logger.info("Agentic AI Console dialog closed.")

    def set_text(self, text: str) -> None:
        """Updates the current text content of the console editor."""
        self.current_text = text

    def execute_live(self, debim_str: Optional[str] = None) -> BuildingModel:
        """
        Parses and evaluates .debim manifest content live, updates history, and notifies callbacks.
        """
        text = debim_str if debim_str is not None else self.current_text
        if text.strip():
            self.history.append(text)

        manifest_dict = parse_debim_str(text)
        building_model = build_geometry(manifest_dict)
        self.last_model = building_model

        if self.on_submit:
            self.on_submit(text, manifest_dict, building_model)

        return building_model


def open_console_dialog(
    on_submit: Optional[Callable[[str, Dict[str, Any], BuildingModel], Any]] = None,
    initial_text: str = "",
    parent: Optional[Any] = None,
) -> AIConsoleDialog:
    """Helper function to create and open an AIConsoleDialog instance."""
    dialog = AIConsoleDialog(on_submit=on_submit, initial_text=initial_text, parent=parent)
    dialog.open()
    return dialog
