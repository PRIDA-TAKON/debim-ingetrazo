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
    Interactive AI Console Dialog abstraction.
    Supports live text input, parsing, and callback notification to update the active viewport.
    """

    def __init__(
        self,
        on_submit: Optional[Callable[[str, Dict[str, Any], BuildingModel], Any]] = None,
        initial_text: str = "",
    ):
        self.on_submit = on_submit
        self.current_text: str = initial_text
        self.history: list[str] = []
        self.is_open: bool = False
        self.last_model: Optional[BuildingModel] = None

    def open(self) -> None:
        """Opens/displays the interactive console dialog."""
        self.is_open = True
        logger.info("Agentic AI Console dialog opened.")

    def close(self) -> None:
        """Closes/hides the console dialog."""
        self.is_open = False
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
) -> AIConsoleDialog:
    """Helper function to create and open an AIConsoleDialog instance."""
    dialog = AIConsoleDialog(on_submit=on_submit, initial_text=initial_text)
    dialog.open()
    return dialog
