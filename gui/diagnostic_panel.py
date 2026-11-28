"""
gui/diagnostic_panel.py — Universal Integration Diagnostic Panel for JARVIS H3.3
Contributed by Aman Kumar (@iamTechieAman).

Real-time diagnostic matrix displaying verified execution status of all JARVIS modules:
  - Tracks Primary Modes, Sidebar Panels, System Automation, and AI Intelligence
  - Enforces honest verification state: OPERATIONAL, DEGRADED, REQUIRES_CONFIG, FAILED
  - Real-time probe trigger to re-verify live subsystems on macOS
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.style import hud_font, px_font
from gui.theme import C

logger = logging.getLogger("diagnostic_panel")


class DiagnosticOverlay(QWidget):
    """Universal Integration Diagnostic Overlay."""

    closed = pyqtSignal()
    _OW = 860
    _OH = 620

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            DiagnosticOverlay {{
                background: rgba(10, 12, 16, 252);
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedSize(self._OW, self._OH)
        self._active_cat = "All"
        self._filter_query = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Header ──────────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("⚡ UNIVERSAL INTEGRATION DIAGNOSTIC MATRIX")
        title.setFont(hud_font(12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        title_box.addWidget(title)

        sub = QLabel("Real-World Execution & Subsystem Verification Ledger · JARVIS Mark-LVII v57.3")
        sub.setFont(px_font(9.5))
        sub.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        title_box.addWidget(sub)
        hdr_row.addLayout(title_box)

        hdr_row.addStretch()

        self._btn_verify = QPushButton("🔄 Re-Verify Subsystems")
        self._btn_verify.setFont(px_font(9.5, QFont.Weight.Bold))
        self._btn_verify.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_verify.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL};
                color: {C.PRI};
                border: 1px solid {C.PRI_DIM};
                border-radius: 4px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background: {C.HOVER};
                border-color: {C.PRI};
            }}
        """)
        self._btn_verify.clicked.connect(self._run_reverification)
        hdr_row.addWidget(self._btn_verify)

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: none; font-size: 14px;")
        close_btn.clicked.connect(self.hide)
        hdr_row.addWidget(close_btn)
        root.addLayout(hdr_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        root.addWidget(sep)

        # ── Controls: Search Bar & Category Filters ──────────────────────────
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Filter features by name, UI component, or status...")
        self._search_input.setFixedHeight(30)
        self._search_input.setFont(px_font(10))
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.PANEL2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{
                border-color: {C.PRI};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search_changed)
        ctrl_row.addWidget(self._search_input, stretch=2)

        self._pills: Dict[str, QPushButton] = {}
        for cat in ["All", "Primary Modes", "Sidebar", "Automation", "Intelligence"]:
            b = QPushButton(cat)
            b.setFixedHeight(28)
            b.setFont(px_font(9.5))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _, c=cat: self._set_category(c))
            self._pills[cat] = b
            ctrl_row.addWidget(b)

        root.addLayout(ctrl_row)

        # ── Scroll Area for Feature Cards ────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: 1px solid {C.BORDER}; border-radius: 6px; }}")

        self._container = QWidget()
        self._container.setStyleSheet("background: transparent;")
        self._cards_lay = QVBoxLayout(self._container)
        self._cards_lay.setContentsMargins(12, 10, 12, 10)
        self._cards_lay.setSpacing(8)

        self._scroll.setWidget(self._container)
        root.addWidget(self._scroll, stretch=1)

        # ── Summary Footer ───────────────────────────────────────────────────
        self._footer_lbl = QLabel()
        self._footer_lbl.setFont(px_font(9.5, mono=True))
        self._footer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        root.addWidget(self._footer_lbl)

        self._update_pills_style()
        self._render_features()

    def _set_category(self, cat: str):
        self._active_cat = cat
        self._update_pills_style()
        self._render_features()

    def _on_search_changed(self, text: str):
        self._filter_query = text.lower().strip()
        self._render_features()

    def _update_pills_style(self):
        for cat, b in self._pills.items():
            if cat == self._active_cat:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PRI_DIM};
                        color: {C.PRI};
                        border: 1px solid {C.PRI};
                        border-radius: 4px;
                        padding: 0 10px;
                        font-weight: bold;
                    }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL};
                        color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER};
                        border-radius: 4px;
                        padding: 0 10px;
                    }}
                    QPushButton:hover {{
                        color: {C.TEXT};
                        border-color: {C.BORDER_B};
                    }}
                """)

    def _clear_cards(self):
        while self._cards_lay.count():
            item = self._cards_lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()

    def _render_features(self):
        self._clear_cards()
        from core.feature_registry import get_feature_registry
        reg = get_feature_registry()
        features = reg.get_all_features()

        total = len(features)
        operational = 0
        displayed = 0

        for f in features:
            status = f.actual_status
            if status == "OPERATIONAL":
                operational += 1

            # Filter logic
            if self._active_cat != "All" and f.category != self._active_cat:
                continue

            if self._filter_query:
                q = self._filter_query
                haystack = f"{f.display_name} {f.ui_component} {f.backend_handler} {f.actual_status} {f.category}".lower()
                if q not in haystack:
                    continue

            displayed += 1
            card = self._build_feature_card(f)
            self._cards_lay.addWidget(card)

        self._cards_lay.addStretch()
        self._footer_lbl.setText(
            f"Subsystems: {operational}/{total} Operational  ·  Filter: {displayed} shown  ·  Ledger: memory/feature_registry.json"
        )

    def _build_feature_card(self, f) -> QWidget:
        w = QFrame()
        w.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 5px; padding: 6px;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 8, 10, 8)
        lay.setSpacing(4)

        # Header row: Name + Category badge + Status badge
        h_row = QHBoxLayout()
        name_lbl = QLabel(f.display_name)
        name_lbl.setFont(px_font(11, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        h_row.addWidget(name_lbl)

        cat_lbl = QLabel(f"[{f.category}]")
        cat_lbl.setFont(px_font(9, mono=True))
        cat_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        h_row.addWidget(cat_lbl)
        h_row.addStretch()

        status_col = C.GREEN if f.actual_status == "OPERATIONAL" else ("#F59E0B" if f.actual_status == "DEGRADED" else C.ERR)
        stat_lbl = QLabel(f"● {f.actual_status}")
        stat_lbl.setFont(px_font(9.5, QFont.Weight.Bold, mono=True))
        stat_lbl.setStyleSheet(f"color: {status_col}; background: transparent;")
        h_row.addWidget(stat_lbl)
        lay.addLayout(h_row)

        # Details
        meta_str = f"• UI Component: {f.ui_component}\n• Handler: {f.backend_handler}\n• Permission: {f.required_permissions}  |  Deps: {', '.join(f.service_dependencies)}"
        meta_lbl = QLabel(meta_str)
        meta_lbl.setFont(px_font(8.5, mono=True))
        meta_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; line-height: 1.3;")
        lay.addWidget(meta_lbl)

        return w

    def _run_reverification(self):
        from core.feature_registry import get_feature_registry
        reg = get_feature_registry()
        reg.run_all_verifications()
        self._render_features()
