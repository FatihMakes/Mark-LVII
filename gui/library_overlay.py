"""
gui/library_overlay.py — Full-Featured Universal Document & Media Library Overlay
Provides browsing, search, file preview, importing, and native macOS viewer integration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QListWidget, QListWidgetItem, QTextEdit, QFrame, QFileDialog, QMessageBox,
    QSplitter, QSizePolicy
)

from gui.style import hud_font, px_font, scroll_css, DISPLAY_CSS
from gui.theme import C
from gui.overlays import _HudOverlay
from core.library_manager import get_library_manager


class LibraryOverlay(_HudOverlay):
    """Universal persistent file library, document reader, and preview overlay."""

    _OW = 860
    _OH = 580

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            LibraryOverlay {{
                background: rgba(12, 12, 12, 252);
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedSize(self._OW, self._OH)
        self.mgr = get_library_manager()
        self._current_files = []
        self._selected_file_path = None
        self._filter_type = None

        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        # ── Header Bar ────────────────────────────────────────────────────────
        hdr_lay = QHBoxLayout()
        hdr_lay.setSpacing(8)

        title = QLabel("📚  UNIVERSAL DOCUMENT & MEDIA LIBRARY")
        title.setFont(hud_font(12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        hdr_lay.addWidget(title)
        hdr_lay.addStretch()

        btn_import = QPushButton("+ Import File")
        btn_import.setFixedHeight(28)
        btn_import.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import.setFont(px_font(10, QFont.Weight.DemiBold))
        btn_import.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL};
                color: {C.WHITE};
                border: 1px solid {C.BORDER_A};
                border-radius: 4px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: {C.HOVER};
                border-color: {C.PRI};
            }}
        """)
        btn_import.clicked.connect(self._do_import_dialog)
        hdr_lay.addWidget(btn_import)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(26, 26)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: none; font-size: 14px;")
        btn_close.clicked.connect(self._do_close)
        hdr_lay.addWidget(btn_close)
        root.addLayout(hdr_lay)

        # ── Search & Filter Controls ──────────────────────────────────────────
        ctrl_lay = QHBoxLayout()
        ctrl_lay.setSpacing(8)

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍  Search documents, notes, reports, or text content...")
        self._search_input.setFixedHeight(32)
        self._search_input.setFont(px_font(11))
        self._search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C.INPUT};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
                padding: 0 12px;
            }}
            QLineEdit:focus {{
                border-color: {C.PRI};
            }}
        """)
        self._search_input.textChanged.connect(self._on_search_changed)
        ctrl_lay.addWidget(self._search_input, stretch=1)

        # Filter Pills
        self._filter_btns = {}
        for cat in ["All", "Document", "Note", "Spreadsheet", "Image", "Code"]:
            b = QPushButton(cat)
            b.setFixedHeight(28)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setFont(px_font(9.5, QFont.Weight.DemiBold))
            b.clicked.connect(lambda _, c=cat: self._set_filter(c))
            ctrl_lay.addWidget(b)
            self._filter_btns[cat] = b
        self._update_filter_styles("All")
        root.addLayout(ctrl_lay)

        # ── Main Body Splitter (File List & Preview Panel) ────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #222; width: 1px; }")

        # Left: File List
        list_container = QWidget()
        list_lay = QVBoxLayout(list_container)
        list_lay.setContentsMargins(0, 0, 8, 0)
        list_lay.setSpacing(4)

        self._file_list = QListWidget()
        self._file_list.setFont(px_font(11))
        self._file_list.setStyleSheet(f"""
            QListWidget {{
                background: {C.PANEL2};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
                padding: 4px;
                color: {C.TEXT};
            }}
            QListWidget::item {{
                padding: 8px 10px;
                border-radius: 4px;
                border-bottom: 1px solid #1a1a1a;
            }}
            QListWidget::item:hover {{
                background: {C.HOVER};
            }}
            QListWidget::item:selected {{
                background: {C.ACTIVE};
                color: {C.PRI};
                border-left: 3px solid {C.PRI};
            }}
        """ + scroll_css())
        self._file_list.currentItemChanged.connect(self._on_file_selected)
        list_lay.addWidget(self._file_list)
        splitter.addWidget(list_container)

        # Right: Detail & Preview Panel
        preview_container = QWidget()
        preview_lay = QVBoxLayout(preview_container)
        preview_lay.setContentsMargins(8, 0, 0, 0)
        preview_lay.setSpacing(8)

        self._preview_title = QLabel("Select a document to inspect preview")
        self._preview_title.setFont(hud_font(10, QFont.Weight.Bold))
        self._preview_title.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        preview_lay.addWidget(self._preview_title)

        self._preview_meta = QLabel("Location: ~/Desktop/JarvisLibrary")
        self._preview_meta.setFont(px_font(9))
        self._preview_meta.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        preview_lay.addWidget(self._preview_meta)

        self._preview_text = QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setFont(px_font(10, mono=True))
        self._preview_text.setStyleSheet(f"""
            QTextEdit {{
                background: {C.PANEL2};
                color: {C.TEXT_MED};
                border: 1px solid {C.BORDER};
                border-radius: 6px;
                padding: 8px;
            }}
        """ + scroll_css())
        preview_lay.addWidget(self._preview_text, stretch=1)

        # Preview Action Buttons
        action_row = QHBoxLayout()
        action_row.setSpacing(8)

        self._btn_open_native = QPushButton("🖥️ Open in macOS Preview")
        self._btn_open_native.setFixedHeight(30)
        self._btn_open_native.setFont(px_font(10, QFont.Weight.DemiBold))
        self._btn_open_native.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL};
                color: {C.PRI};
                border: 1px solid {C.BORDER_A};
                border-radius: 4px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: {C.HOVER};
                border-color: {C.PRI};
            }}
        """)
        self._btn_open_native.clicked.connect(self._do_open_native)
        action_row.addWidget(self._btn_open_native)

        self._btn_delete = QPushButton("🗑️ Delete")
        self._btn_delete.setFixedHeight(30)
        self._btn_delete.setFont(px_font(10, QFont.Weight.DemiBold))
        self._btn_delete.setStyleSheet(f"""
            QPushButton {{
                background: {C.PANEL};
                color: {C.RED};
                border: 1px solid {C.BORDER};
                border-radius: 4px;
                padding: 0 10px;
            }}
            QPushButton:hover {{
                background: {C.HOVER};
                border-color: {C.RED};
            }}
        """)
        self._btn_delete.clicked.connect(self._do_delete)
        action_row.addWidget(self._btn_delete)
        action_row.addStretch()

        preview_lay.addLayout(action_row)
        splitter.addWidget(preview_container)
        splitter.setSizes([360, 480])

        root.addWidget(splitter, stretch=1)

    def _set_filter(self, cat: str):
        self._filter_type = None if cat == "All" else cat
        self._update_filter_styles(cat)
        self._refresh_list()

    def _update_filter_styles(self, active_cat: str):
        for name, btn in self._filter_btns.items():
            if name == active_cat:
                btn.setStyleSheet(f"background: {C.ACTIVE}; color: {C.PRI}; border: 1px solid {C.BORDER_A}; border-radius: 12px; padding: 0 8px;")
            else:
                btn.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: 1px solid transparent; border-radius: 12px; padding: 0 8px;")

    def _on_search_changed(self, text: str):
        if text.strip():
            self._current_files = self.mgr.search_library(text)
        else:
            self._current_files = self.mgr.list_files(file_type=self._filter_type, recursive=True)
        self._render_file_items()

    def _refresh_list(self):
        query = self._search_input.text().strip()
        if query:
            self._current_files = self.mgr.search_library(query)
        else:
            self._current_files = self.mgr.list_files(file_type=self._filter_type, recursive=True)
        self._render_file_items()

    def _render_file_items(self):
        self._file_list.clear()
        if not self._current_files:
            item = QListWidgetItem("No files found in Library.")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self._file_list.addItem(item)
            self._preview_title.setText("Library Empty")
            self._preview_text.setPlainText("Use '+ Import File' above or ask JARVIS to generate documents.")
            return

        for f in self._current_files:
            icon_str = self._icon_for_type(f["type"])
            label = f"{icon_str}  {f['name']}  ({f['size_str']})"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, f["path"])
            self._file_list.addItem(item)

        self._file_list.setCurrentRow(0)

    def _on_file_selected(self, current: QListWidgetItem, previous=None):
        if not current:
            return
        path_str = current.data(Qt.ItemDataRole.UserRole)
        if not path_str or not Path(path_str).exists():
            return

        self._selected_file_path = path_str
        p = Path(path_str)
        self._preview_title.setText(p.name)
        self._preview_meta.setText(f"Size: {self.mgr._format_size(p.stat().st_size)}  •  Path: {p}")

        # Load content preview
        text = self.mgr.read_document_text(path_str, max_chars=4000)
        self._preview_text.setPlainText(text)

    def _do_open_native(self):
        if not self._selected_file_path:
            return
        self.mgr.open_in_macos_viewer(self._selected_file_path)

    def _do_import_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Document to Import into JARVIS Library",
            str(Path.home()),
            "All Documents (*.pdf *.docx *.xlsx *.csv *.md *.txt *.png *.jpg);;All Files (*)"
        )
        if file_path:
            res = self.mgr.import_document(file_path, dest_folder="Documents")
            self._refresh_list()

    def _do_delete(self):
        if not self._selected_file_path:
            return
        p = Path(self._selected_file_path)
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to permanently delete '{p.name}' from your Library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.mgr.delete_item(self._selected_file_path, confirmed=True)
            self._selected_file_path = None
            self._refresh_list()

    def _icon_for_type(self, cat: str) -> str:
        if cat == "Document":
            return "📄"
        elif cat == "Spreadsheet":
            return "📊"
        elif cat == "Image":
            return "🖼️"
        elif cat == "Note":
            return "📝"
        elif cat == "Code":
            return "💻"
        return "📁"
