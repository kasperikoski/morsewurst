# ============================================================
# morsewurst/ui/controllers/layout_controller.py
# ============================================================

from __future__ import annotations

from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import ttk

import morsewurst.config as config

from morsewurst.ui.panels.control_panel import build_control_panel
from morsewurst.ui.panels.general_info_panel import build_general_info_panel
from morsewurst.ui.panels.history_panel import build_history_panel
from morsewurst.ui.panels.problems_panel import build_problems_panel
from morsewurst.ui.panels.result_panel import build_result_panel
from morsewurst.ui.panels.serial_panel import build_serial_panel
from morsewurst.ui.panels.settings_panel import build_settings_panel
from morsewurst.ui.panels.skill_panel import build_skill_panel
from morsewurst.ui.panels.training_panel import build_training_panel

if TYPE_CHECKING:
    from morsewurst.ui.app import MorsewurstApp


class LayoutController:
    """Owns the main application layout and panel construction."""

    def __init__(self, app: "MorsewurstApp") -> None:
        self.app = app

    def build_ui(self) -> None:
        """Build the main two-column application UI."""
        app = self.app

        outer = ttk.Frame(app, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        right = ttk.Frame(
            outer,
            width=getattr(config, "UI_RIGHT_WIDTH", 740),
        )
        right.pack(side=tk.RIGHT, fill=tk.Y, expand=False, padx=(10, 0))
        right.pack_propagate(False)

        left = ttk.Frame(outer)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        build_training_panel(app, left)

        middle_row = ttk.Frame(
            left,
            height=getattr(config, "UI_SUMMARY_ROW_HEIGHT", 185),
        )
        middle_row.pack(fill=tk.X, pady=(0, 0))
        middle_row.pack_propagate(False)

        result_column = ttk.Frame(middle_row)
        result_column.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        info_column = ttk.Frame(
            middle_row,
            width=getattr(config, "UI_GENERAL_INFO_WIDTH", 360),
        )
        info_column.pack(side=tk.LEFT, fill=tk.BOTH, padx=(10, 0))
        info_column.pack_propagate(False)

        build_result_panel(app, result_column)
        build_general_info_panel(app, info_column)
        build_control_panel(app, left)
        build_history_panel(app, left)
        build_settings_panel(app, right)
        build_skill_panel(app, right)
        build_serial_panel(app, right)
        build_problems_panel(app, right)