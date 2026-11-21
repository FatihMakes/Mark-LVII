"""gui/perplexity_workspace.py — Central Workspace for Perplexity AI Experience.

Houses 3 distinct experiences:
- MODE 1: AI SEARCH MODE (Research-focused, citations, sources, related questions)
- MODE 2: PERSONAL ASSISTANT MODE (Conversational chat, coding, document studio)
- MODE 3: JARVIS VOICE HUD MODE (Animated 3D Siri/Perplexity reactor orb & holographic face)

Includes top navigation with mode switcher pills, engine indicator, and context panel toggle.
"""
from __future__ import annotations

import re
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QClipboard, QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QStackedWidget, QTextBrowser, QTextEdit,
    QVBoxLayout, QWidget,
)

from gui.style import DISPLAY_CSS, MONO_CSS, hud_font, px_font, scroll_css
from gui.theme import C


class SuggestionPill(QPushButton):
    """Clickable suggestion chip on the welcome screen."""

    def __init__(self, icon: str, text: str, parent=None):
        super().__init__(parent)
        self.setText(f"{icon}  {text}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(34)
        self.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 8px;
                padding: 0 14px;
                font-family: {DISPLAY_CSS};
                font-size: 12px;
                font-weight: 500;
                text-align: left;
            }}
            QPushButton:hover {{
                background: {C.PANEL2};
                border-color: {C.PRI_DIM};
                color: {C.WHITE};
            }}
        """)


class ChatMessageCard(QFrame):
    """User or Assistant message bubble with markdown formatting and copy actions."""

    def __init__(self, sender: str, text: str, parent=None):
        super().__init__(parent)
        self._text = text
        is_user = sender.upper() == "YOU"

        bg_col = C.PANEL2 if is_user else C.PANEL
        border_col = C.BORDER_A if is_user else C.BORDER

        self.setStyleSheet(f"""
            QFrame {{
                background: {bg_col};
                border: 1px solid {border_col};
                border-radius: 10px;
                padding: 10px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(6)

        # Header row: Sender badge + timestamp + copy button
        hdr = QHBoxLayout()
        hdr.setSpacing(6)

        badge = QLabel("👤 YOU" if is_user else "⚡ JARVIS")
        badge.setFont(px_font(10, QFont.Weight.Bold))
        badge.setStyleSheet(f"color: {C.PRI if is_user else C.GREEN}; background: transparent; letter-spacing: 1px;")
        hdr.addWidget(badge)
        hdr.addStretch()

        copy_btn = QPushButton("Copy")
        copy_btn.setFixedSize(46, 20)
        copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        copy_btn.setFont(px_font(9, QFont.Weight.DemiBold))
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                color: {C.PRI};
                border-color: {C.PRI};
            }}
        """)
        copy_btn.clicked.connect(self._copy_text)
        hdr.addWidget(copy_btn)
        lay.addLayout(hdr)

        # Message body: Markdown rendered text browser
        self._body = QTextBrowser()
        self._body.setOpenExternalLinks(True)
        self._body.setFont(px_font(13))
        self._body.setFrameShape(QFrame.Shape.NoFrame)
        self._body.setStyleSheet(f"""
            QTextBrowser {{
                background: transparent;
                color: {C.TEXT};
                border: none;
                selection-background-color: {C.PRI_GHO};
            }}
        """ + scroll_css())

        if any(sym in text for sym in ("# ", "## ", "### ", "**", "```", "- ", "* ", "1. ", "|")):
            try:
                self._body.setMarkdown(text)
            except Exception:
                self._body.setPlainText(text)
        else:
            self._body.setPlainText(text)

        # Auto size height based on content
        self._body.document().adjustSize()
        doc_h = int(self._body.document().size().height())
        self._body.setMinimumHeight(min(max(40, doc_h + 10), 450))

        lay.addWidget(self._body)

    def _copy_text(self):
        cb = QApplication.clipboard()
        if cb:
            cb.setText(self._text)


class PerplexityWorkspace(QWidget):
    """Central container managing the 3 main user experiences."""

    prompt_selected        = pyqtSignal(str)   # when a suggestion is clicked
    mode_changed           = pyqtSignal(int)   # 0: Search, 1: Assistant, 2: Voice HUD
    engine_clicked         = pyqtSignal()
    context_panel_toggled  = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active_mode = 0

        self.setStyleSheet(f"background: {C.BG};")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Top Minimal Navigation Bar ────────────────────────────────────
        root.addWidget(self._build_top_nav())

        # ── Main Stacked View (3 Modes) ───────────────────────────────────
        self._stack = QStackedWidget()

        # Mode 1: AI Search View
        self._search_view = self._build_search_view()
        self._stack.addWidget(self._search_view)

        # Mode 2: Personal Assistant View
        self._chat_view = self._build_chat_view()
        self._stack.addWidget(self._chat_view)

        # Mode 3: Voice HUD View Container (placeholder, filled via set_hud_widget)
        self._hud_container = QWidget()
        self._hud_lay = QVBoxLayout(self._hud_container)
        self._hud_lay.setContentsMargins(0, 0, 0, 0)
        self._hud_lay.setSpacing(0)
        self._stack.addWidget(self._hud_container)

        root.addWidget(self._stack, stretch=1)
        self.set_mode(0)

    def _build_top_nav(self) -> QWidget:
        nav = QWidget()
        nav.setFixedHeight(46)
        nav.setStyleSheet(f"""
            QWidget {{
                background: {C.BG};
                border-bottom: 1px solid {C.BORDER};
            }}
        """)
        lay = QHBoxLayout(nav)
        lay.setContentsMargins(14, 0, 14, 0)
        lay.setSpacing(10)

        # Mode selector pills in top header
        self._mode_pills = []
        pills_data = [("🌐 AI Search", 0), ("💬 Assistant", 1), ("⚛ Voice HUD", 2)]
        for label, idx in pills_data:
            b = QPushButton(label)
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFont(px_font(11, QFont.Weight.DemiBold))
            b.clicked.connect(lambda _, i=idx: self.set_mode(i))
            self._mode_pills.append(b)
            lay.addWidget(b)

        lay.addStretch()

        # Engine Status Pill (clickable to open providers)
        self._engine_btn = QPushButton("● GEMINI LIVE")
        self._engine_btn.setFixedHeight(26)
        self._engine_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._engine_btn.setFont(px_font(10, QFont.Weight.Bold, mono=True))
        self._engine_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL2};
                color: {C.GREEN};
                border: 1px solid {C.BORDER_A};
                border-radius: 13px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                border-color: {C.GREEN};
            }}
        """)
        self._engine_btn.clicked.connect(self.engine_clicked.emit)
        lay.addWidget(self._engine_btn)

        # Context Panel Toggle Pill
        self._context_btn = QPushButton("◨ Context Panel")
        self._context_btn.setFixedHeight(26)
        self._context_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._context_btn.setFont(px_font(11, QFont.Weight.DemiBold))
        self._context_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                color: {C.PRI};
                border-color: {C.PRI_DIM};
            }}
        """)
        self._context_btn.clicked.connect(self.context_panel_toggled.emit)
        lay.addWidget(self._context_btn)

        return nav

    # ── MODE 1: AI Search View (Perplexity) ────────────────────────────────
    def _build_search_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 4)
        lay.setSpacing(10)

        # Scroll area for conversation / search results
        self._search_scroll = QScrollArea()
        self._search_scroll.setWidgetResizable(True)
        self._search_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._search_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }" + scroll_css())

        self._search_content = QWidget()
        self._search_content.setStyleSheet("background: transparent;")
        self._search_lay = QVBoxLayout(self._search_content)
        self._search_lay.setContentsMargins(0, 0, 0, 0)
        self._search_lay.setSpacing(12)

        # Hero Welcome Section
        self._search_hero = QWidget()
        self._search_hero.setStyleSheet("background: transparent;")
        hero_lay = QVBoxLayout(self._search_hero)
        hero_lay.setContentsMargins(10, 30, 10, 20)
        hero_lay.setSpacing(12)
        hero_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        h_title = QLabel("Good to see you. How can I help?")
        h_title.setFont(hud_font(20, QFont.Weight.Bold))
        h_title.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        h_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_lay.addWidget(h_title)

        h_sub = QLabel("Search the web, solve complex academic assignments, or analyze code with real citations.")
        h_sub.setFont(px_font(13))
        h_sub.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        h_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero_lay.addWidget(h_sub)

        # Suggestion Pills Grid
        grid_w = QWidget()
        grid_w.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_w)
        grid.setSpacing(8)

        suggestions = [
            ("🌐", "Explain quantum computing from first principles"),
            ("🛡", "Audit system security score & vulnerabilities"),
            ("📈", "Generate quantitative trading signals for NVDA"),
            ("📑", "Solve cloud security question bank unit 1 to 3 PDF"),
            ("⚡", "Compare AI Agent frameworks: LangGraph vs Autogen vs AGY"),
            ("📰", "What are the latest AI and tech breakthroughs today?"),
        ]
        for idx, (icon, text) in enumerate(suggestions):
            pill = SuggestionPill(icon, text)
            pill.clicked.connect(lambda _, t=text: self.prompt_selected.emit(t))
            grid.addWidget(pill, idx // 2, idx % 2)

        hero_lay.addWidget(grid_w)
        self._search_lay.addWidget(self._search_hero)
        self._search_lay.addStretch()

        self._search_scroll.setWidget(self._search_content)
        lay.addWidget(self._search_scroll, stretch=1)
        return w

    # ── MODE 2: Personal Assistant View ───────────────────────────────────
    def _build_chat_view(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 12, 16, 4)
        lay.setSpacing(10)

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._chat_scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }" + scroll_css())

        self._chat_content = QWidget()
        self._chat_content.setStyleSheet("background: transparent;")
        self._chat_lay = QVBoxLayout(self._chat_content)
        self._chat_lay.setContentsMargins(0, 0, 0, 0)
        self._chat_lay.setSpacing(12)

        # Chat Hero Welcome
        self._chat_hero = QWidget()
        self._chat_hero.setStyleSheet("background: transparent;")
        c_hero_lay = QVBoxLayout(self._chat_hero)
        c_hero_lay.setContentsMargins(10, 30, 10, 20)
        c_hero_lay.setSpacing(10)
        c_hero_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        c_title = QLabel("JARVIS Personal Assistant")
        c_title.setFont(hud_font(20, QFont.Weight.Bold))
        c_title.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        c_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_hero_lay.addWidget(c_title)

        c_sub = QLabel("Autonomous coding agent, document studio, system diagnostics, and communication hub.")
        c_sub.setFont(px_font(13))
        c_sub.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        c_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        c_hero_lay.addWidget(c_sub)

        c_grid_w = QWidget()
        c_grid_w.setStyleSheet("background: transparent;")
        c_grid = QGridLayout(c_grid_w)
        c_grid.setSpacing(8)

        chat_suggestions = [
            ("💻", "Inspect this repository and clean temp caches"),
            ("📄", "Generate a detailed cover letter and PDF on desktop"),
            ("💬", "WhatsApp Mummy saying I will be home in 10 minutes"),
            ("🧩", "List installed plugins and system capabilities"),
        ]
        for idx, (icon, text) in enumerate(chat_suggestions):
            pill = SuggestionPill(icon, text)
            pill.clicked.connect(lambda _, t=text: self.prompt_selected.emit(t))
            c_grid.addWidget(pill, idx // 2, idx % 2)

        c_hero_lay.addWidget(c_grid_w)
        self._chat_lay.addWidget(self._chat_hero)
        self._chat_lay.addStretch()

        self._chat_scroll.setWidget(self._chat_content)
        lay.addWidget(self._chat_scroll, stretch=1)
        return w

    def set_hud_widget(self, w: QWidget):
        """Embeds the existing HUD canvas & stack into Mode 3."""
        self._hud_lay.addWidget(w)

    def set_mode(self, idx: int):
        self._active_mode = idx
        self._stack.setCurrentIndex(idx)
        for i, pill in enumerate(self._mode_pills):
            if i == idx:
                pill.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL2};
                        color: {C.PRI};
                        border: 1px solid {C.PRI_DIM};
                        border-radius: 6px;
                        padding: 0 12px;
                    }}
                """)
            else:
                pill.setStyleSheet(f"""
                    QPushButton {{
                        background: transparent;
                        color: {C.TEXT_MED};
                        border: 1px solid transparent;
                        border-radius: 6px;
                        padding: 0 12px;
                    }}
                    QPushButton:hover {{
                        background: {C.PANEL};
                        color: {C.TEXT};
                    }}
                """)
        self.mode_changed.emit(idx)

    def get_mode(self) -> int:
        return self._active_mode

    def set_engine_label(self, label: str):
        self._engine_btn.setText(f"● {label.upper()}")

    def add_user_message(self, text: str):
        # Hide heroes
        self._search_hero.hide()
        self._chat_hero.hide()

        card = ChatMessageCard("YOU", text)
        target_lay = self._search_lay if self._active_mode == 0 else self._chat_lay
        target_lay.insertWidget(target_lay.count() - 1, card)
        self._scroll_to_bottom()

    def add_assistant_message(self, text: str):
        self._search_hero.hide()
        self._chat_hero.hide()

        card = ChatMessageCard("JARVIS", text)
        target_lay = self._search_lay if self._active_mode == 0 else self._chat_lay
        target_lay.insertWidget(target_lay.count() - 1, card)
        self._scroll_to_bottom()

    def clear_conversation(self):
        # Clean both search and chat views
        for lay, hero in ((self._search_lay, self._search_hero), (self._chat_lay, self._chat_hero)):
            for i in reversed(range(lay.count() - 1)):
                item = lay.itemAt(i)
                if item and item.widget() and item.widget() != hero:
                    w = item.widget()
                    lay.removeWidget(w)
                    w.deleteLater()
            hero.show()

    def _scroll_to_bottom(self):
        scroll = self._search_scroll if self._active_mode == 0 else self._chat_scroll
        QApplication.processEvents()
        vs = scroll.verticalScrollBar()
        if vs:
            vs.setValue(vs.maximum())
