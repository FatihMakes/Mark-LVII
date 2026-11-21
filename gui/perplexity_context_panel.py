"""gui/perplexity_context_panel.py — Contextual Right Information Panel for Perplexity UI.

Provides 4 clean tabs:
1. Sources: Citations, source cards, domains, and web links from AI research.
2. Communications: The original LogWidget / Activity Log (ALL voice turns, system logs, error messages).
3. Activity: Hardware & system telemetry (CPU, Memory, GPU, Temp gauges, Network sparkline, Status rows).
4. Tasks: Active background tasks and scheduled routines.
"""
from __future__ import annotations

import re
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
    QStackedWidget, QVBoxLayout, QWidget,
)

from gui.style import DISPLAY_CSS, MONO_CSS, hud_font, px_font, scroll_css
from gui.theme import C
from gui.widgets import HoloPanel, LogWidget


class SourceCard(QFrame):
    """Clean citation card inspired by Perplexity."""

    def __init__(self, index: int, title: str, domain: str, snippet: str = "", url: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: {C.PANEL2};
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                padding: 6px;
            }}
            QFrame:hover {{
                border-color: {C.PRI_DIM};
                background: #17233d;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(3)

        top_row = QHBoxLayout()
        top_row.setSpacing(4)

        num_lbl = QLabel(f"[{index}]")
        num_lbl.setFont(px_font(10, QFont.Weight.Bold, mono=True))
        num_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        top_row.addWidget(num_lbl)

        dom_lbl = QLabel(domain)
        dom_lbl.setFont(px_font(10, QFont.Weight.DemiBold))
        dom_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        top_row.addWidget(dom_lbl)
        top_row.addStretch()
        lay.addLayout(top_row)

        t_lbl = QLabel(title)
        t_lbl.setFont(px_font(12, QFont.Weight.DemiBold))
        t_lbl.setWordWrap(True)
        t_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        lay.addWidget(t_lbl)

        if snippet:
            snip_lbl = QLabel(snippet[:140] + ("..." if len(snippet) > 140 else ""))
            snip_lbl.setFont(px_font(10))
            snip_lbl.setWordWrap(True)
            snip_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(snip_lbl)


class PerplexityContextPanel(QWidget):
    """Contextual tabbed right panel."""

    close_requested = pyqtSignal()

    def __init__(self, log_widget: LogWidget, parent=None):
        super().__init__(parent)
        self._log_widget = log_widget
        self.setFixedWidth(310)
        self.setStyleSheet(f"""
            QWidget#PerplexityContextPanel {{
                background: {C.BG};
                border-left: 1px solid {C.BORDER};
            }}
        """)
        self.setObjectName("PerplexityContextPanel")

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 10, 8, 10)
        root.setSpacing(8)

        # ── Top Bar: Tab Switcher + Close Button ───────────────────────────
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(2, 0, 2, 4)
        top_bar.setSpacing(4)

        self._tab_btns = []
        tab_names = [("Sources", "📑"), ("Comms", "💬"), ("Activity", "📊"), ("Tasks", "⚡")]
        for i, (name, icon) in enumerate(tab_names):
            b = QPushButton(f"{icon} {name}")
            b.setFixedHeight(26)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFont(px_font(10, QFont.Weight.DemiBold))
            b.clicked.connect(lambda _, idx=i: self.set_current_tab(idx))
            self._tab_btns.append(b)
            top_bar.addWidget(b)

        top_bar.addStretch()

        self._close_btn = QPushButton("✕")
        self._close_btn.setFixedSize(22, 22)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.setToolTip("Collapse panel")
        self._close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT_DIM};
                border: none;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {C.PRI};
            }}
        """)
        self._close_btn.clicked.connect(self.close_requested.emit)
        top_bar.addWidget(self._close_btn)
        root.addLayout(top_bar)

        # ── Stacked Views ─────────────────────────────────────────────────
        self._stack = QStackedWidget()

        # 1. Sources Tab View
        self._sources_page = self._build_sources_page()
        self._stack.addWidget(self._sources_page)

        # 2. Communications Log Tab View (Original LogWidget!)
        self._comms_page = self._build_comms_page()
        self._stack.addWidget(self._comms_page)

        # 3. Activity / Telemetry Tab View (Metrics, gauges, sparkline)
        self._activity_page = QWidget()
        self._activity_lay = QVBoxLayout(self._activity_page)
        self._activity_lay.setContentsMargins(0, 0, 0, 0)
        self._activity_lay.setSpacing(6)
        self._stack.addWidget(self._activity_page)

        # 4. Tasks Tab View (Background tasks & routines)
        self._tasks_page = QWidget()
        self._tasks_lay = QVBoxLayout(self._tasks_page)
        self._tasks_lay.setContentsMargins(0, 0, 0, 0)
        self._tasks_lay.setSpacing(6)
        self._stack.addWidget(self._tasks_page)

        root.addWidget(self._stack, stretch=1)
        self.set_current_tab(1)  # Default to Communications log so voice turns are instantly visible

    def _build_sources_page(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        header = QLabel("RESEARCH SOURCES & CITATIONS")
        header.setFont(px_font(10, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        lay.addWidget(header)

        self._sources_scroll = QScrollArea()
        self._sources_scroll.setWidgetResizable(True)
        self._sources_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._sources_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }" + scroll_css())

        self._sources_container = QWidget()
        self._sources_container.setStyleSheet("background: transparent;")
        self._sources_list_lay = QVBoxLayout(self._sources_container)
        self._sources_list_lay.setContentsMargins(0, 0, 0, 0)
        self._sources_list_lay.setSpacing(6)

        self._empty_sources_lbl = QLabel(
            "No active search sources yet.\nAsk a question in AI Search mode to view citations."
        )
        self._empty_sources_lbl.setFont(px_font(11))
        self._empty_sources_lbl.setWordWrap(True)
        self._empty_sources_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; padding: 12px 0;")
        self._sources_list_lay.addWidget(self._empty_sources_lbl)
        self._sources_list_lay.addStretch()

        self._sources_scroll.setWidget(self._sources_container)
        lay.addWidget(self._sources_scroll, stretch=1)
        return w

    def _build_comms_page(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)

        header = QLabel("COMMUNICATIONS & VOICE TRANSCRIPTS")
        header.setFont(px_font(10, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        lay.addWidget(header)

        # Embed original log widget directly!
        lay.addWidget(self._log_widget, stretch=1)
        return w

    def set_current_tab(self, idx: int):
        self._stack.setCurrentIndex(idx)
        for i, b in enumerate(self._tab_btns):
            if i == idx:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2};
                        color: {C.PRI};
                        border: 1px solid {C.BORDER_A};
                        border-radius: 4px;
                        padding: 0 6px;
                    }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {C.TEXT_DIM};
                        border: 1px solid transparent;
                        border-radius: 4px;
                        padding: 0 6px;
                    }}
                    QPushButton:hover {{
                        color: {C.TEXT};
                        background: {C.PANEL};
                    }}
                """)

    def set_activity_widget(self, w: QWidget):
        self._activity_lay.addWidget(w, stretch=1)

    def set_tasks_widget(self, w: QWidget):
        self._tasks_lay.addWidget(w, stretch=1)

    def add_source(self, index: int, title: str, domain: str, snippet: str = "", url: str = ""):
        self._empty_sources_lbl.hide()
        card = SourceCard(index, title, domain, snippet, url)
        # Insert before stretch
        self._sources_list_lay.insertWidget(self._sources_list_lay.count() - 1, card)

    def clear_sources(self):
        # Remove cards
        for i in reversed(range(self._sources_list_lay.count() - 1)):
            item = self._sources_list_lay.itemAt(i)
            if item and item.widget() and item.widget() != self._empty_sources_lbl:
                w = item.widget()
                self._sources_list_lay.removeWidget(w)
                w.deleteLater()
        self._empty_sources_lbl.show()

    def parse_and_display_sources_from_text(self, text: str):
        """Extracts source links/domains from search or research output and populates cards."""
        urls = re.findall(r'https?://(?:www\.)?([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})(/[^\s\)]*)?', text)
        if urls:
            self.clear_sources()
            seen = set()
            idx = 1
            for domain, path in urls:
                if domain not in seen and len(seen) < 8:
                    seen.add(domain)
                    full = f"https://{domain}{path}"
                    self.add_source(idx, f"Source from {domain}", domain, full, full)
                    idx += 1
            self.set_current_tab(0)
