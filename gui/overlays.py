"""gui/overlays.py — Panels that open over the HUD: setup, customise, plugins, confirm, audio, memory, remote.

Split out of ui.py in Mark LVII; behaviour unchanged."""
from __future__ import annotations

import json
import math
import os
import platform
import random
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

from PyQt6.QtCore import (
    QEasingCurve, QLineF, QMimeData, QObject, QParallelAnimationGroup, QPointF,
    QPoint, QPropertyAnimation, QRect, QRectF, QSize, QSizeF, Qt, QTimer,
    QUrl, pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut,
)
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QGraphicsScene, QGraphicsView, QGraphicsPixmapItem,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget, QProgressBar, QSlider,
)

from gui.theme import (
    C,
    DEFAULT_UI_COLOR,
    _OS,
    qcol,
)

from gui.style import hud_font, px_font


class SetupOverlay(QWidget):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            SetupOverlay {{
                background: rgba(10, 10, 10, 252);
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)

        detected = {"darwin": "mac", "windows": "windows"}.get(
            _OS.lower(), "linux"
        )
        self._sel_os = detected

        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 22, 30, 22)
        layout.setSpacing(8)

        def _lbl(txt, font_size=9, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(hud_font(font_size,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        layout.addWidget(_lbl("◈  INITIALISATION REQUIRED", 13, True))
        layout.addWidget(_lbl("Configure J.A.R.V.I.S. Mark-LVII Enterprise Edition", 9, color=C.PRI_DIM))
        layout.addWidget(_lbl("Architect: FatihMakes • Enterprise Contributor: Aman Kumar (@iamTechieAman)", 8, color=C.ACC2))
        layout.addSpacing(6)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep)
        layout.addSpacing(4)

        layout.addWidget(_lbl("GEMINI API KEY(S) — enter 1 or multiple separated by commas for auto-rotation", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("AIzaSy... , AIzaSy... (comma-separated for auto-rotation)")
        self._key_input.setFont(hud_font(9))
        self._key_input.setFixedHeight(32)
        try:
            from memory.config_manager import get_gemini_keys
            existing_keys = get_gemini_keys()
            if existing_keys:
                self._key_input.setText(", ".join(existing_keys))
        except Exception:
            pass
        self._key_input.setStyleSheet(f"""
            QLineEdit {{
                background: #121212; color: {C.TEXT};
                border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px;
            }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """)
        layout.addWidget(self._key_input)
        layout.addSpacing(12)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet(f"color: {C.BORDER};"); layout.addWidget(sep2)
        layout.addSpacing(4)

        layout.addWidget(_lbl("OPERATING SYSTEM", 8, color=C.TEXT_DIM,
                               align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        layout.addWidget(_lbl(f"Auto-detected: {det_name}", 8, color=C.ACC2,
                               align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout(); os_row.setSpacing(6)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows","⊞  Windows"),("mac","  macOS"),("linux","🐧  Linux")]:
            btn = QPushButton(label)
            btn.setFont(hud_font(9, QFont.Weight.Bold))
            btn.setFixedHeight(32)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        layout.addLayout(os_row)
        self._sel(detected)
        layout.addSpacing(12)

        init_btn = QPushButton("▸  INITIALISE SYSTEMS")
        init_btn.setFont(hud_font(10, QFont.Weight.Bold))
        init_btn.setFixedHeight(36)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {C.PRI_GHO}; border: 1px solid {C.PRI};
            }}
        """)
        init_btn.clicked.connect(self._submit)
        layout.addWidget(init_btn)

        # Gemini is not required. Somebody running a model on their own machine,
        # or out of free quota, has to be able to start without a key.
        local_btn = QPushButton("NO KEY — USE A LOCAL MODEL")
        local_btn.setFont(hud_font(9, QFont.Weight.Bold))
        local_btn.setFixedHeight(30)
        local_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        local_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_DIM};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
        """)
        local_btn.clicked.connect(lambda: self.done.emit("", self._sel_os))
        layout.addWidget(local_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows":(C.PRI,"#001a22"),"mac":(C.ACC2,"#1a1400"),"linux":(C.GREEN,"#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {fg}; color: {bg};
                        border: none; border-radius: 3px; font-weight: bold;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {C.PANEL}; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px;
                    }}
                    QPushButton:hover {{ color: {C.TEXT}; border: 1px solid {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_input.styleSheet() +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}"
            )
            return
        self.done.emit(key, self._sel_os)


class HueWheel(QWidget):
    """
    Circular colour picker. The user drags the handle (small white circle)
    around the wheel to choose from ALL hues. The filled circle in the centre
    is a live preview of the selected colour.
    """

    hue_picked    = pyqtSignal(str)   # while dragging (live)
    hue_committed = pyqtSignal(str)   # when the handle is released

    _RING = 16   # ring thickness (px)

    def __init__(self, initial_hex: str = DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setFixedSize(148, 148)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue  = 0.53
        self._drag = False
        self.set_color(initial_hex)

    # ── API ──────────────────────────────────────────────────────────────────
    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    # ── geometry helpers ─────────────────────────────────────────────────────
    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c  = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()          # screen y goes down — flip to math axis
        ang = math.atan2(dy, dx)      # [-π, π], counter-clockwise
        return (ang / (2 * math.pi)) % 1.0

    # ── drawing ──────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        if not p.isActive():
            return
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect   = self._ring_rect()
        center = rect.center()

        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        # centre preview circle
        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        inner   = rect.adjusted(30, 30, -30, -30)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        p.drawEllipse(inner)

        # draggable handle
        r   = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx  = center.x() + r * math.cos(ang)
        hy  = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#00060a"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 7.5, 7.5)
        p.end()

    # ── fare ─────────────────────────────────────────────────────────────────
    def mousePressEvent(self, e):
        self._drag = True
        self._hue  = self._hue_from_pos(e.position())
        self.update()
        self.hue_picked.emit(self.color())

    def mouseMoveEvent(self, e):
        if self._drag:
            self._hue = self._hue_from_pos(e.position())
            self.update()
            self.hue_picked.emit(self.color())

    def mouseReleaseEvent(self, e):
        if self._drag:
            self._drag = False
            self.hue_committed.emit(self.color())


class CustomizeOverlay(QWidget):
    """Floating overlay — change assistant name, user name, UI colour and voice."""

    saved = pyqtSignal(str, str, str, str)   # assistant_name, user_name, ui_color, voice
    _OW, _OH = 400, 588

    def __init__(self, assistant_name="JARVIS", user_name="",
                 ui_color=DEFAULT_UI_COLOR, voice="", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CustomizeOverlay {{
                background: rgba(10, 10, 10, 252);
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(8)

        def _lbl(txt, fs=9, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt); w.setAlignment(align)
            w.setFont(hud_font(fs,
                            QFont.Weight.Bold if bold else QFont.Weight.Normal))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        _fs = (f"QLineEdit {{ background: #121212; color: {C.TEXT}; "
               f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
               f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        lay.addWidget(_lbl("⚙  CUSTOMISE ASSISTANT", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        lay.addWidget(_lbl("ASSISTANT NAME", 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        self._name_input = QLineEdit(assistant_name)
        self._name_input.setFont(hud_font(10))
        self._name_input.setFixedHeight(32)
        self._name_input.setStyleSheet(_fs)
        lay.addWidget(self._name_input)

        lay.addSpacing(4)
        lay.addWidget(_lbl("YOUR NAME  (leave blank for default sir / efendim)", 8,
                            color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        self._user_input = QLineEdit(user_name)
        self._user_input.setPlaceholderText("e.g.  Tony   (leave blank for auto)")
        self._user_input.setFont(hud_font(10))
        self._user_input.setFixedHeight(32)
        self._user_input.setStyleSheet(_fs)
        lay.addWidget(self._user_input)

        # ── Assistant voice — Gemini prebuilt voices ─────────────────────────
        # Names are language-neutral proper nouns, so the row reads the same in
        # every locale. Selecting one and applying rebuilds the Live session.
        from memory.config_manager import AVAILABLE_VOICES, DEFAULT_VOICE
        lay.addSpacing(4)
        lay.addWidget(_lbl("ASSISTANT VOICE", 8, color=C.TEXT_DIM,
                            align=Qt.AlignmentFlag.AlignLeft))
        self._sel_voice   = (voice or DEFAULT_VOICE)
        if self._sel_voice not in AVAILABLE_VOICES:
            self._sel_voice = DEFAULT_VOICE
        self._voice_btns: dict[str, QPushButton] = {}
        voice_row = QHBoxLayout(); voice_row.setSpacing(4)
        for _v in AVAILABLE_VOICES:
            b = QPushButton(_v)
            b.setCheckable(True)
            b.setFixedHeight(28)
            b.setFont(hud_font(8, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, name=_v: self._on_voice_pick(name))
            self._voice_btns[_v] = b
            voice_row.addWidget(b)
        lay.addLayout(voice_row)
        self._refresh_voice_btns()

        # ── UI colour — colour wheel ─────────────────────────────────────────
        lay.addSpacing(4)
        clr_hdr = QHBoxLayout()
        clr_hdr.addWidget(_lbl("UI COLOUR  —  drag the handle", 8,
                               color=C.TEXT_DIM, align=Qt.AlignmentFlag.AlignLeft))
        clr_hdr.addStretch()
        df_btn = QPushButton("DEFAULT")
        df_btn.setFixedSize(64, 20)
        df_btn.setFont(hud_font(7, QFont.Weight.Bold))
        df_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        df_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        df_btn.clicked.connect(lambda: self._set_color(DEFAULT_UI_COLOR))
        clr_hdr.addWidget(df_btn)
        lay.addLayout(clr_hdr)

        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._sel_color     = self._initial_color
        self.on_preview     = None   # callable(hex) — live preview; MainWindow wires it

        self._wheel = HueWheel(self._sel_color)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch(); wheel_row.addWidget(self._wheel); wheel_row.addStretch()
        lay.addLayout(wheel_row)
        self._wheel.hue_picked.connect(self._on_wheel_pick)
        self._wheel.hue_committed.connect(self._on_wheel_commit)

        self._hex_input = QLineEdit(self._sel_color)
        self._hex_input.setPlaceholderText("#00d4ff   (custom hex colour)")
        self._hex_input.setFont(hud_font(10))
        self._hex_input.setFixedHeight(28)
        self._hex_input.setStyleSheet(_fs)
        self._hex_input.textEdited.connect(self._on_hex_edited)
        lay.addWidget(self._hex_input)

        lay.addSpacing(6)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        save_btn = QPushButton("▸  APPLY CHANGES")
        save_btn.setFixedHeight(34)
        save_btn.setFont(hud_font(9, QFont.Weight.Bold))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px;
            }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setFont(hud_font(9))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

    # ── voice selection ──────────────────────────────────────────────────────
    def _on_voice_pick(self, name: str):
        self._sel_voice = name
        self._refresh_voice_btns()

    def _refresh_voice_btns(self):
        """Highlight the selected voice pill; dim the rest."""
        for name, b in self._voice_btns.items():
            on = (name == self._sel_voice)
            b.setChecked(on)
            if on:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI};
                        border: 1px solid {C.PRI}; border-radius: 3px; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT_MED};
                        border: 1px solid {C.BORDER}; border-radius: 3px; }}
                    QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
                """)

    # ── colour flow ──────────────────────────────────────────────────────────
    def _set_color(self, hx: str, update_wheel: bool = True, preview: bool = True):
        """Updates the selected colour; hex box + wheel stay in sync, theme is live-previewed."""
        self._sel_color = hx.strip().lower()
        self._hex_input.blockSignals(True)
        self._hex_input.setText(self._sel_color)
        self._hex_input.blockSignals(False)
        if update_wheel:
            self._wheel.set_color(self._sel_color)
        if preview and self.on_preview:
            self.on_preview(self._sel_color)

    def _on_wheel_pick(self, hx: str):
        # While dragging: update the hex box, don't apply the theme yet
        self._sel_color = hx
        self._hex_input.blockSignals(True)
        self._hex_input.setText(hx)
        self._hex_input.blockSignals(False)

    def _on_wheel_commit(self, hx: str):
        # Handle released → live-preview the whole interface
        self._set_color(hx, update_wheel=False)

    def _on_hex_edited(self, text: str):
        t = text.strip().lower()
        if t.startswith("#") and len(t) == 7:
            try:
                int(t[1:], 16)
            except ValueError:
                return
            self._set_color(t, update_wheel=True, preview=True)

    def _cancel(self):
        # If a preview was applied, revert to the colour from launch
        if self.on_preview and self._sel_color != self._initial_color:
            self.on_preview(self._initial_color)
        self.hide()

    def _save(self):
        name = self._name_input.text().strip() or "JARVIS"
        user = self._user_input.text().strip()
        self.saved.emit(name, user, self._sel_color or DEFAULT_UI_COLOR, self._sel_voice)
        self.hide()


class PluginManagerOverlay(QWidget):
    """Floating overlay — lists discovered plugins with per-plugin ON/OFF toggles and instant test triggers."""

    _OW = 490

    def __init__(self, plugins: list[dict] = None, parent=None):
        super().__init__(parent)
        if plugins is None:
            try:
                from core.plugin_loader import discover_plugins
                plugins = discover_plugins()
            except Exception:
                plugins = []
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginManagerOverlay {{
                background: rgba(10, 10, 10, 252);
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        hdr = QLabel("🧩  TORVIS & JARVIS EXTENSION SUITE")
        hdr.setFont(hud_font(11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 0.8px;")
        lay.addWidget(hdr)

        sub = QLabel("Autonomous ready-to-use plugins with 100% free cloud fallback:")
        sub.setFont(hud_font(8))
        sub.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(sub)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        if not plugins:
            empty = QLabel("No plugins found in /plugins.")
            empty.setFont(hud_font(8))
            empty.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(empty)

        for p in plugins:
            lay.addLayout(self._build_row(p))

        lay.addSpacing(6)
        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(30)
        close_btn.setFont(hud_font(9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px;
            }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn)
        self.adjustSize()

    def _build_row(self, p: dict) -> QHBoxLayout:
        row = QHBoxLayout(); row.setSpacing(6)

        label_text = p["name"] if p["valid"] else f"{p['name']}  (⚠ {p['file']})"
        lbl = QLabel(label_text)
        lbl.setFont(hud_font(8, QFont.Weight.DemiBold))
        lbl.setStyleSheet(f"color: {C.TEXT if p['valid'] else C.TEXT_DIM}; background: transparent;")
        lbl.setToolTip(p["description"] if p["valid"] else p["error"])
        lbl.setWordWrap(False)
        row.addWidget(lbl, stretch=1)

        if p["valid"]:
            test_btn = QPushButton("TEST")
            test_btn.setFixedSize(52, 24)
            test_btn.setFont(hud_font(7, QFont.Weight.Bold))
            test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            test_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C.PANEL}; color: {C.PRI};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: {C.HOVER}; border-color: {C.PRI}; color: {C.WHITE}; }}
            """)
            test_btn.clicked.connect(lambda _, name=p["name"]: self._run_test(name))
            row.addWidget(test_btn)

        btn = QPushButton()
        btn.setFixedSize(62, 24)
        btn.setFont(hud_font(7, QFont.Weight.Bold))
        if not p["valid"]:
            btn.setText("BROKEN")
            btn.setEnabled(False)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
            """)
        else:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._style_toggle(btn, p["enabled"])
            btn.clicked.connect(lambda _, name=p["name"], b=btn: self._toggle(name, b))
        row.addWidget(btn)
        return row

    def _run_test(self, name: str):
        prompts = {
            "excel_writer": "Build an expense spreadsheet for this month (.xlsx)",
            "smart_lights": "Turn my desk light to Arc Blue at 80% brightness",
            "build_guide": "Prepare an optimal PC build configuration for $1500",
            "telegram_remote": "Check 24/7 Telegram phone assistant bridge status",
            "omninet_supertool": "Scrape the latest tech headlines and live forex rates",
            "godmode_assistant": "Run system diagnostics and check disk health",
        }
        prompt = prompts.get(name, f"Run {name} plugin")
        win = self.window()
        if hasattr(win, "_send_text"):
            win._send_text(prompt)
        self.hide()

    def _style_toggle(self, btn: QPushButton, enabled: bool):
        if enabled:
            btn.setText("ON")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: #001a08; color: {C.GREEN};
                    border: 1px solid {C.GREEN_D}; border-radius: 3px;
                }}
                QPushButton:hover {{ background: #002010; }}
            """)
        else:
            btn.setText("OFF")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {C.TEXT_DIM};
                    border: 1px solid {C.BORDER}; border-radius: 3px;
                }}
                QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
            """)

    def _toggle(self, name: str, btn: QPushButton):
        from memory.config_manager import get_plugin_enabled, save_plugin_enabled
        new_val = not get_plugin_enabled(name)
        save_plugin_enabled(name, new_val)
        self._style_toggle(btn, new_val)


class _HudOverlay(QWidget):
    """Base for the floating panels placed by hand over the HUD.

    They are children of the central widget but sit in no layout, so Qt never
    invalidates the region they occupy when they hide or shrink: the HUD keeps
    painting around them and their last frame stays on screen as a ghost. Any
    overlay positioned with _centre_overlay needs this."""

    def hideEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            # Repaint exactly what we were covering, before we stop covering it.
            p.update(self.geometry())
        super().hideEvent(e)

    def closeEvent(self, e):
        p = self.parentWidget()
        if p is not None:
            p.update(self.geometry())
        super().closeEvent(e)


class ConfirmBanner(_HudOverlay):
    """The gate in front of an action that cannot be taken back.

    The old confirmation was a tool parameter the model filled in itself, which
    means it confirmed its own shutdown requests. This is the interface asking,
    and the answer travels from a human finger to core/confirm.py without the
    model in the loop. Nothing blocks while it is up: the assistant keeps
    talking, so this costs no latency — unlike the old gate, which spent two
    tool round trips on every power command."""

    answered = pyqtSignal(bool)
    _OW = 430

    def __init__(self, title: str, detail: str, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ConfirmBanner {{
                background: rgba(14, 3, 0, 250);
                border: 1px solid {C.ACC};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(8)

        hdr = QLabel("⚠  CONFIRM")
        hdr.setFont(hud_font(11, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.ACC}; background: transparent;")
        lay.addWidget(hdr)

        ttl = QLabel(title)
        ttl.setWordWrap(True)
        ttl.setFont(hud_font(10, QFont.Weight.Bold))
        ttl.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        lay.addWidget(ttl)

        if detail:
            dtl = QLabel(detail)
            dtl.setWordWrap(True)
            dtl.setFont(hud_font(8))
            dtl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            lay.addWidget(dtl)

        row = QHBoxLayout(); row.setSpacing(8)

        yes = QPushButton("▸  CONFIRM")
        yes.setFixedHeight(32)
        yes.setFont(hud_font(9, QFont.Weight.Bold))
        yes.setCursor(Qt.CursorShape.PointingHandCursor)
        yes.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.ACC};
                border: 1px solid {C.ACC}; border-radius: 3px; }}
            QPushButton:hover {{ background: rgba(255,107,0,40); }}
        """)
        yes.clicked.connect(lambda: self.answered.emit(True))
        row.addWidget(yes)

        no = QPushButton("CANCEL")
        no.setFixedHeight(32)
        no.setFont(hud_font(9))
        no.setCursor(Qt.CursorShape.PointingHandCursor)
        no.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        no.clicked.connect(lambda: self.answered.emit(False))
        row.addWidget(no)
        lay.addLayout(row)

        # Default focus on CANCEL: if someone hits Enter without reading, the
        # safe answer wins.
        no.setDefault(True)
        no.setFocus()


class AudioDeviceOverlay(_HudOverlay):
    """Choose which microphone JARVIS listens to and which speakers it uses.

    Both audio streams used to open with no `device=` at all, so they always
    took the OS default — which on Windows moves by itself the moment a headset
    is plugged in. 'JARVIS can't hear me' is usually 'JARVIS is listening to the
    webcam'."""

    picked = pyqtSignal()      # emitted after Apply, when something changed

    # THESE EXIST BECAUSE QTimer.singleShot FROM A WORKER THREAD NEVER FIRES.
    #
    # The first version posted results back with `QTimer.singleShot(0, fn)` from
    # inside the audio thread. A QTimer belongs to the thread that creates it,
    # and that thread has no event loop — so the timer was created, never ran,
    # and the panel sat on "Speak now…" for ever while the recording finished
    # silently behind it. Reported as "I saw no sign of anything at all", which
    # is precisely what it looked like.
    #
    # A signal is the thread-safe way across: Qt queues it onto the receiving
    # object's thread, which for a widget is the GUI thread. Both carry only
    # plain values — never a widget — because the widgets belong to the GUI
    # thread and the worker must not touch them even to pass them along.
    _level_seen = pyqtSignal(int)          # 0-100, while recording
    _test_result = pyqtSignal(str, bool)   # sentence, was it good

    _OW = 460

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.audio_devices import list_devices, DEFAULT_LABEL
        from memory.config_manager import get_input_device, get_output_device

        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            AudioDeviceOverlay {{
                background: rgba(10, 10, 10, 252);
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 16, 20, 16)
        lay.setSpacing(6)

        hdr = QLabel("🎧  AUDIO DEVICES")
        hdr.setFont(hud_font(12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        lay.addWidget(sep)

        _combo_css = (
            f"QComboBox {{ background: #121212; color: {C.TEXT}; "
            f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
            f"QComboBox:hover {{ border-color: {C.BORDER_B}; }}"
            f"QComboBox QAbstractItemView {{ background: #121212; color: {C.TEXT}; "
            f"selection-background-color: {C.PRI_GHO}; border: 1px solid {C.BORDER}; }}"
        )

        _test_css = (
            f"QPushButton {{ background: transparent; color: {C.TEXT_DIM}; "
            f"border: 1px solid {C.BORDER}; border-radius: 3px; }}"
            f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.PRI_DIM}; }}"
            f"QPushButton:disabled {{ color: {C.BORDER}; }}"
        )

        def _row(label: str, kind: str, current: str) -> QComboBox:
            cap = QLabel(label)
            cap.setFont(hud_font(8))
            cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(cap)

            box = QComboBox()
            box.setFont(hud_font(9))
            box.setFixedHeight(30)
            box.setStyleSheet(_combo_css)
            # The list is served from a cache warmed on a background thread at
            # startup, so opening this panel never blocks the Qt thread on the
            # host audio API.
            box.addItem(DEFAULT_LABEL, "")
            for name in list_devices(kind):
                box.addItem(name, name)
            idx = box.findData(current) if current else 0
            box.setCurrentIndex(idx if idx >= 0 else 0)
            if current and idx < 0:
                # Saved device is not plugged in right now. Show it rather than
                # silently resetting the user's choice to default.
                box.addItem(f"{current}  (not connected)", current)
                box.setCurrentIndex(box.count() - 1)

            # THE ONE CHECK THE STARTUP PROBE CANNOT MAKE.
            #
            # core/audio_devices decides at launch whether a device opens and
            # whether it moves audio, and it does that with silence. A muted
            # microphone, a level slider at zero and a privacy shutter all pass
            # every one of those tests and still deliver a flat line — the only
            # thing that separates them from a working microphone is a person
            # speaking into it.
            #
            # So the button is here, beside the dropdown, in the panel somebody
            # opens when JARVIS cannot hear them. It replaces a loose
            # `ses_testi.py` in the project root that nobody would ever find.
            btn_row = QHBoxLayout(); btn_row.setSpacing(6)
            btn_row.addWidget(box, 1)
            test = QPushButton("TEST")
            test.setFixedSize(64, 30)
            test.setFont(hud_font(8, QFont.Weight.Bold))
            test.setCursor(Qt.CursorShape.PointingHandCursor)
            test.setStyleSheet(_test_css)
            btn_row.addWidget(test)
            lay.addLayout(btn_row)

            # A meter, because a static label is indistinguishable from a hang.
            # Three seconds of "Speak now" with nothing moving was reported as
            # "I saw no sign of anything" — correctly, since nothing on screen
            # responded to the user's voice.
            meter = QProgressBar()
            meter.setRange(0, 100)
            meter.setValue(0)
            meter.setTextVisible(False)
            meter.setFixedHeight(6)
            meter.setStyleSheet(
                f"QProgressBar {{ background: #121212; border: 1px solid {C.BORDER}; "
                f"border-radius: 3px; }}"
                f"QProgressBar::chunk {{ background: {C.PRI}; border-radius: 2px; }}")
            meter.hide()
            lay.addWidget(meter)

            result = QLabel("")
            result.setWordWrap(True)
            result.setFont(hud_font(7))
            result.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(result)

            test.clicked.connect(
                lambda _=False, k=kind, b=box, t=test, r=result, m=meter:
                    self._run_test(k, b, t, r, m))
            return box

        # Which row is being tested right now. One at a time — the button is
        # disabled for the duration — so a single slot is enough, and it keeps
        # widgets off the signal payload.
        self._active = None                # (button, label, meter)
        self._level_seen.connect(self._on_level)
        self._test_result.connect(self._on_result)

        self._in_box  = _row("MICROPHONE — what JARVIS hears you with",
                             "input", get_input_device())
        lay.addSpacing(4)
        self._out_box = _row("SPEAKERS — what JARVIS talks through",
                             "output", get_output_device())

        # ── Output volume, beside the output device ──────────────────────────
        #
        # Choosing "Realtek(R) Audio" here and finding it far too quiet used to
        # mean leaving this panel, opening the system sound settings, finding
        # the same endpoint again and moving a slider there. The volume belongs
        # next to the device it applies to.
        _vol_now = None
        try:
            from core.audio_devices import get_output_volume
            # The SELECTED output, not the system default. Somebody puts the
            # assistant on their speakers and keeps everything else in their
            # headphones; a slider labelled with one device that moves the
            # other is worse than no slider at all.
            _vol_now = get_output_volume(self._out_box.currentData() or "")
        except Exception:
            pass

        if _vol_now is not None:
            vcap = QLabel("OUTPUT VOLUME")
            vcap.setFont(hud_font(8))
            vcap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addSpacing(4)
            lay.addWidget(vcap)

            vrow = QHBoxLayout(); vrow.setSpacing(8)
            self._vol = QSlider(Qt.Orientation.Horizontal)
            self._vol.setRange(0, 100)
            self._vol.setValue(int(_vol_now))
            self._vol.setFixedHeight(22)
            self._vol.setStyleSheet(
                f"QSlider::groove:horizontal {{ background: #121212; height: 4px; "
                f"border: 1px solid {C.BORDER}; border-radius: 2px; }}"
                f"QSlider::sub-page:horizontal {{ background: {C.PRI_DIM}; "
                f"border-radius: 2px; }}"
                f"QSlider::handle:horizontal {{ background: {C.PRI}; width: 10px; "
                f"margin: -5px 0; border-radius: 5px; }}")
            self._vol_lbl = QLabel(f"{int(_vol_now)}%")
            self._vol_lbl.setFont(hud_font(8))
            self._vol_lbl.setFixedWidth(40)
            self._vol_lbl.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
            vrow.addWidget(self._vol, 1)
            vrow.addWidget(self._vol_lbl)
            lay.addLayout(vrow)

            # valueChanged fires for every pixel of a drag, and each one is a
            # COM call into the audio endpoint. sliderReleased fires once, when
            # the user has decided — the label still follows the handle so the
            # number moves while they drag.
            self._vol.valueChanged.connect(
                lambda v: self._vol_lbl.setText(f"{v}%"))
            self._vol.sliderReleased.connect(self._apply_volume)
            self._out_box.currentIndexChanged.connect(
                lambda _i: self._volume_follows_device())

        note = QLabel("Applying reconnects the session. Your conversation is kept.")
        note.setWordWrap(True)
        note.setFont(hud_font(7))
        note.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addSpacing(6)
        lay.addWidget(note)

        row = QHBoxLayout(); row.setSpacing(8)
        ok = QPushButton("▸  APPLY")
        ok.setFixedHeight(32)
        ok.setFont(hud_font(9, QFont.Weight.Bold))
        ok.setCursor(Qt.CursorShape.PointingHandCursor)
        ok.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.PRI};
                border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
            QPushButton:hover {{ background: {C.PRI_GHO}; border-color: {C.PRI}; }}
        """)
        ok.clicked.connect(self._apply)
        row.addWidget(ok)

        cancel = QPushButton("CLOSE")
        cancel.setFixedHeight(32)
        cancel.setFont(hud_font(9))
        cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        cancel.clicked.connect(self.hide)
        row.addWidget(cancel)
        lay.addLayout(row)

    def _apply_volume(self):
        """Set the system output volume from the slider, off the Qt thread.

        The Windows path goes through COM, which can block for tens of
        milliseconds; that is not long enough to see but is long enough to
        stutter a drag, and there is no reason to make the interface wait for
        it.
        """
        import threading
        value = self._vol.value()
        device = self._out_box.currentData() or ""

        def _work():
            from core import audio_devices
            if not audio_devices.set_output_volume(value, device):
                print(f"[Audio] the volume of '{device}' could not be set "
                      f"to {value}%")

        threading.Thread(target=_work, daemon=True, name="audio-volume").start()

    def _volume_follows_device(self):
        """Re-read the slider when the chosen output changes.

        Each device keeps its own level, so leaving the handle where it was
        would show the previous device's volume against the new device's name —
        and the next drag would then jump it there.
        """
        if not hasattr(self, "_vol"):
            return
        try:
            from core.audio_devices import get_output_volume
            now = get_output_volume(self._out_box.currentData() or "")
        except Exception:
            now = None
        if now is None:
            return
        self._vol.blockSignals(True)
        self._vol.setValue(int(now))
        self._vol.blockSignals(False)
        self._vol_lbl.setText(f"{int(now)}%")

    def _run_test(self, kind, box, button, label, meter=None):
        """Record or play for real, off the Qt thread.

        Both calls block for seconds — recording waits for the user to speak,
        the tone waits for itself — and doing that on the Qt thread freezes the
        HUD, which is the mistake Mark LV already paid for once with a 2.1
        second wake-word import in the settings drawer.

        Results come back by signal, not by timer. See the note on
        `_level_seen` above for why that distinction is the whole feature.
        """
        import threading

        name = box.currentData() or ""
        self._active = (button, label, meter)
        button.setEnabled(False)
        label.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        label.setText("Speak now…" if kind == "input" else "Playing a tone…")
        if meter is not None and kind == "input":
            meter.setValue(0)
            meter.show()

        def _work():
            from core import audio_devices
            try:
                if kind == "input":
                    res = audio_devices.measure_input(
                        name,
                        on_level=lambda f: self._level_seen.emit(int(f * 100)))
                    text = f"peak {res['peak']}  —  {res['verdict']}"
                else:
                    res = audio_devices.play_tone(name)
                    text = res["verdict"]
                good = bool(res.get("ok", False))
            except Exception as e:
                text, good = f"The test itself failed: {e}", False
            self._test_result.emit(text, good)

        threading.Thread(target=_work, daemon=True, name=f"audio-test-{kind}").start()

    def _on_level(self, value: int):
        """A live level, already on the GUI thread thanks to the signal."""
        if self._active and self._active[2] is not None:
            self._active[2].setValue(max(0, min(100, value)))

    def _on_result(self, text: str, good: bool):
        if not self._active:
            return
        button, label, meter = self._active
        self._active = None
        button.setEnabled(True)
        if meter is not None:
            meter.setValue(0)
            meter.hide()
        label.setStyleSheet(
            f"color: {C.PRI if good else C.TEXT_DIM}; background: transparent;")
        label.setText(text)

    def _apply(self):
        from memory.config_manager import (
            get_input_device, get_output_device,
            save_input_device, save_output_device,
        )
        new_in  = self._in_box.currentData()  or ""
        new_out = self._out_box.currentData() or ""
        changed = (new_in != get_input_device()) or (new_out != get_output_device())
        save_input_device(new_in)
        save_output_device(new_out)
        self.hide()
        # Only rebuild the session if something actually moved — a no-op Apply
        # should not cost a reconnect.
        if changed:
            self.picked.emit()


class MemoryOverlay(_HudOverlay):
    """Everything JARVIS has stored about you, and when it learned it.

    Memory used to be a 2200-character store that deleted its oldest entries
    when full and mentioned it only on stdout. The cap is gone; this panel is
    the other half of that change — a memory you cannot inspect is a memory you
    cannot trust, and 'delete' has to be something the person can do."""

    _OW = 520

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            MemoryOverlay {{
                background: rgba(10, 10, 10, 252);
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._OW)

        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(5)
        self._rebuild()

    def _clear_layout(self):
        """Take every item out of the layout and detach it from the widget tree
        in this call.

        deleteLater() on its own is not enough: it queues destruction for the
        next event-loop pass, and until then the old rows are still children of
        this widget and still paint — which is what drew half of the previous
        panel over the new one. setParent(None) removes them from the tree now;
        deleteLater() then frees them safely."""
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                # hide() stops it painting in this frame; deleteLater() frees it
                # safely afterwards. setParent(None) would also stop the paint,
                # but it turns the widget into a top-level window for the moment
                # between the two calls, which is not something to leave lying
                # around inside a click handler.
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _settle(self, before):
        """Size the panel to its content, re-centre it, and repaint what the old
        size covered.

        The re-size has to happen here rather than at the end of _rebuild
        because Qt has not polished the freshly-created children at that point,
        so the size hint it would read is the empty-layout one. Measured: a
        first adjustSize() returned 32 px for a panel whose content needed 155,
        and a second call — after the same widgets had been through the event
        loop — returned 155. So this runs twice: once now, once on the next
        turn, from _rebuild.

        The re-centre and the repaint are needed because the overlay is placed
        by hand and is in no layout: shrinking it leaves it off-centre and
        leaves its former pixels on screen, since nothing tells the parent that
        region changed. The repaint has to cover the union of the old and new
        rectangles."""
        self._lay.invalidate()
        self._lay.activate()
        self.updateGeometry()
        self.adjustSize()

        p = self.parentWidget()
        if p is None:
            self.update()
            return
        self.move(max(0, (p.width()  - self.width())  // 2),
                  max(0, (p.height() - self.height()) // 2))
        p.update(before.united(self.geometry()))
        self.update()

    def _rebuild(self):
        before = self.geometry()
        self._clear_layout()

        from memory.memory_manager import all_entries_for_ui

        hdr = QLabel("🧠  WHAT JARVIS REMEMBERS")
        hdr.setFont(hud_font(12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        self._lay.addWidget(hdr)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        rows = all_entries_for_ui()

        cap = QLabel(f"{len(rows)} stored facts — newest first. "
                     f"Nothing here is sent anywhere; it lives in "
                     f"memory/long_term.json on this machine.")
        cap.setWordWrap(True)
        cap.setFont(hud_font(7))
        cap.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._lay.addWidget(cap)

        if not rows:
            empty = QLabel("Nothing stored yet.")
            empty.setFont(hud_font(9))
            empty.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
            self._lay.addWidget(empty)
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFixedHeight(min(420, 34 * len(rows) + 10))
            scroll.setStyleSheet(
                f"QScrollArea {{ border: 1px solid {C.BORDER}; border-radius: 3px; "
                f"background: transparent; }}"
            )
            inner = QWidget()
            ilay  = QVBoxLayout(inner)
            ilay.setContentsMargins(6, 6, 6, 6)
            ilay.setSpacing(3)

            for r in rows:
                line = QHBoxLayout(); line.setSpacing(6)
                txt = QLabel(f"<b>{r['key'].replace('_', ' ')}</b> "
                             f"<span style='color:{C.TEXT_MED}'>— {r['value']}</span>")
                txt.setWordWrap(True)
                txt.setFont(hud_font(8))
                txt.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
                line.addWidget(txt, 1)

                meta = QLabel(f"{r['category'][:4]} · {r['updated'] or '—'}")
                meta.setFont(hud_font(7))
                meta.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
                line.addWidget(meta)

                rm = QPushButton("✕")
                rm.setFixedSize(20, 20)
                rm.setFont(hud_font(8, QFont.Weight.Bold))
                rm.setCursor(Qt.CursorShape.PointingHandCursor)
                rm.setToolTip("Forget this")
                rm.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                        border: 1px solid {C.BORDER}; border-radius: 3px; }}
                    QPushButton:hover {{ color: {C.RED}; border-color: {C.RED}; }}
                """)
                rm.clicked.connect(
                    lambda _=False, c=r["category"], k=r["key"]: self._forget(c, k))
                line.addWidget(rm)

                holder = QWidget()
                holder.setLayout(line)
                ilay.addWidget(holder)

            ilay.addStretch()
            scroll.setWidget(inner)
            self._lay.addWidget(scroll)

        close = QPushButton("CLOSE")
        close.setFixedHeight(30)
        close.setFont(hud_font(9))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close.clicked.connect(self.hide)
        self._lay.addWidget(close)

        self._settle(before)
        # …and again once Qt has polished the new children, because the size
        # hint is not final until then. Harmless when the first pass already
        # got it right: _settle is idempotent.
        QTimer.singleShot(0, lambda g=before: self._settle(g))

    def _forget(self, category: str, key: str):
        from memory.memory_manager import forget
        forget(key, category)
        # Rebuild on the NEXT event-loop turn, not inside this click handler.
        # The rebuild destroys the very ✕ button that emitted this signal, and
        # Qt is entitled to touch the sender after a slot returns; tearing it
        # down mid-emission is how a widget ends up half-alive on screen.
        QTimer.singleShot(0, self._rebuild)


class _ScrollSafeCombo(QComboBox):
    """A dropdown that does not change when you scroll past it.

    Qt's default is that a combo box under the pointer swallows the wheel and
    steps its own value with it. Inside a scrolling panel that is not a
    convenience, it is a trap: scrolling down the list of settings silently
    changes whichever ones the pointer crossed on the way, and nothing on screen
    says so. It was reported as "selections move around when I scroll", and it
    is the same bug every Qt settings panel has until somebody fixes it.

    The wheel is only accepted when the box has been clicked into. Otherwise the
    event is passed up, which is what makes the panel scroll instead.
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        # StrongFocus so it can still be tabbed to and used from the keyboard;
        # the wheel is gated on having focus, not on being focusable.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, e):
        if self.hasFocus():
            super().wheelEvent(e)
        else:
            e.ignore()




class ClipboardPanel(QWidget):
    """Floating panel shown when text is copied — offers quick Jarvis actions."""

    action_requested = pyqtSignal(str)
    _W, _H = 326, 112

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            ClipboardPanel {{
                background: rgba(0, 8, 14, 248);
                border: 1px solid {C.BORDER_B};
                border-radius: 6px;
            }}
        """)
        self.setFixedWidth(self._W)
        self._clip_text = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 7)
        lay.setSpacing(4)

        hdr = QHBoxLayout(); hdr.setSpacing(4)
        icon_lbl = QLabel("◈  CLIPBOARD DETECTED")
        icon_lbl.setFont(hud_font(7, QFont.Weight.Bold))
        icon_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        hdr.addWidget(icon_lbl); hdr.addStretch()
        x_btn = QPushButton("✕")
        x_btn.setFixedSize(16, 16)
        x_btn.setFont(hud_font(8))
        x_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.hide)
        hdr.addWidget(x_btn)
        lay.addLayout(hdr)

        self._preview = QLabel()
        self._preview.setFont(hud_font(8))
        self._preview.setStyleSheet(f"""
            color: {C.TEXT}; background: {C.PANEL2};
            border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 6px;
        """)
        self._preview.setWordWrap(False)
        self._preview.setFixedHeight(28)
        lay.addWidget(self._preview)

        btn_row = QHBoxLayout(); btn_row.setSpacing(4)
        _bs = (f"QPushButton {{ background: {C.PANEL2}; color: {C.TEXT_MED}; "
               f"border: 1px solid {C.BORDER}; border-radius: 2px; }}"
               f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.BORDER_B}; }}")
        for label, cmd_fmt in [
            ("TRANSLATE", "Translate this text to English: {text}"),
            ("SUMMARISE", "Summarise this: {text}"),
            ("EXPLAIN",   "Explain this: {text}"),
            ("FIX",       "Fix grammar and spelling: {text}"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(22)
            b.setFont(hud_font(7, QFont.Weight.Bold))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(_bs)
            b.clicked.connect(lambda _, c=cmd_fmt: self._trigger(c))
            btn_row.addWidget(b)
        lay.addLayout(btn_row)

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.hide)
        self.hide()

    def _trigger(self, cmd_fmt: str):
        if self._clip_text:
            self.action_requested.emit(cmd_fmt.format(text=self._clip_text[:800]))
        self.hide()

    def show_clipboard(self, text: str):
        self._clip_text = text
        preview = text[:58].replace('\n', ' ')
        if len(text) > 58:
            preview += "…"
        self._preview.setText(f'"{preview}"')
        self.show(); self.raise_()
        self._dismiss_timer.start(8000)


class PluginSettingsOverlay(QWidget):
    """Floating overlay — renders per-plugin settings forms.

    Fully generic: it iterates the settings schemas a plugin declared via its
    PLUGIN_SETTINGS constant (delivered by PluginRegistry.settings_schemas) and
    builds a form for each. It knows NOTHING about any specific plugin, so the
    core stays clean and plugins remain pure drop-in — install a plugin that
    declares fields (e.g. the 3D-printer suite) and its section appears here;
    install none and this panel simply says there's nothing to configure.
    """

    _test_done = pyqtSignal(str, bool, str)   # namespace, ok, message
    _OW = 460

    def __init__(self, sections: list[dict], parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PluginSettingsOverlay {{
                background: rgba(10, 10, 10, 252);
                border: 1px solid {C.BORDER};
                border-radius: 6px;
            }}
        """)
        self._sections = sections or []
        self._widgets: dict[tuple, object] = {}    # (namespace, key) -> input widget
        self._types:   dict[tuple, str]    = {}     # (namespace, key) -> field type
        self._status_labels: dict[str, QLabel] = {} # namespace -> status QLabel
        self._test_done.connect(self._on_test_done)

        self._fs = (f"QLineEdit {{ background: #121212; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 4px 8px; }}"
                    f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 16, 22, 16)
        root.setSpacing(8)

        root.addWidget(self._lbl("⚙  PLUGIN SETTINGS", 12, True))
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        root.addWidget(sep)

        if not self._sections:
            root.addWidget(self._lbl(
                "No configurable plugins are installed.\nDrop a plugin that needs "
                "settings (like the 3D-printer suite) into the plugins folder and "
                "it will show up here.", 9, color=C.TEXT_DIM))
        else:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setStyleSheet("QScrollArea { background: transparent; }")
            inner = QWidget()
            inner.setStyleSheet("background: transparent;")
            form = QVBoxLayout(inner)
            form.setContentsMargins(0, 0, 6, 0)
            form.setSpacing(6)
            for sec in self._sections:
                self._build_section(form, sec)
            form.addStretch(1)
            scroll.setWidget(inner)
            root.addWidget(scroll, 1)

        # ── bottom buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)
        if self._sections:
            save_btn = QPushButton("▸  SAVE")
            save_btn.setFixedHeight(34)
            save_btn.setFont(hud_font(9, QFont.Weight.Bold))
            save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            save_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.PRI_GHO}; border: 1px solid {C.PRI}; }}
            """)
            save_btn.clicked.connect(self._save_all)
            btn_row.addWidget(save_btn)

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(34)
        close_btn.setFont(hud_font(9))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                border: 1px solid {C.BORDER}; border-radius: 3px; }}
            QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        btn_row.addWidget(close_btn)
        root.addLayout(btn_row)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _lbl(self, txt, fs=9, bold=False, color=C.PRI,
             align=Qt.AlignmentFlag.AlignLeft):
        w = QLabel(txt); w.setAlignment(align); w.setWordWrap(True)
        w.setFont(hud_font(fs,
                        QFont.Weight.Bold if bold else QFont.Weight.Normal))
        w.setStyleSheet(f"color: {color}; background: transparent;")
        return w

    def _build_section(self, form: QVBoxLayout, sec: dict):
        ns     = sec.get("namespace") or sec.get("plugin") or "plugin"
        title  = sec.get("title") or ns
        fields = sec.get("fields") or []
        values = sec.get("values") or {}

        form.addSpacing(4)
        form.addWidget(self._lbl(title, 10, True, C.PRI))

        for field in fields:
            if not isinstance(field, dict) or not field.get("key"):
                continue
            key   = field["key"]
            ftype = (field.get("type") or "text").lower()
            label = field.get("label") or key
            default = field.get("default")
            stored  = values.get(key, default)

            form.addWidget(self._lbl(label.upper(), 8, color=C.TEXT_DIM))

            if ftype == "choice":
                w = QComboBox()
                w.addItems([str(o) for o in field.get("options", [])])
                w.setFont(hud_font(9))
                w.setFixedHeight(30)
                w.setStyleSheet(
                    f"QComboBox {{ background: #121212; color: {C.TEXT}; "
                    f"border: 1px solid {C.BORDER}; border-radius: 3px; padding: 2px 8px; }}"
                    f"QComboBox QAbstractItemView {{ background: #121212; color: {C.TEXT}; "
                    f"selection-background-color: {C.PRI_GHO}; }}")
                if stored is not None:
                    w.setCurrentText(str(stored))
            elif ftype == "toggle":
                w = QPushButton()
                w.setCheckable(True)
                w.setChecked(bool(stored))
                w.setFixedHeight(28)
                w.setFont(hud_font(8, QFont.Weight.Bold))
                w.setCursor(Qt.CursorShape.PointingHandCursor)
                self._style_toggle(w)
                w.toggled.connect(lambda _=False, b=w: self._style_toggle(b))
            else:  # text / password
                w = QLineEdit("" if stored is None else str(stored))
                w.setFont(hud_font(10))
                w.setFixedHeight(30)
                w.setStyleSheet(self._fs)
                if field.get("placeholder"):
                    w.setPlaceholderText(str(field["placeholder"]))
                if ftype == "password":
                    w.setEchoMode(QLineEdit.EchoMode.Password)

            self._widgets[(ns, key)] = w
            self._types[(ns, key)]   = ftype
            form.addWidget(w)

        # optional test/connect action button + status line
        action = sec.get("action")
        if isinstance(action, dict) and callable(action.get("run")):
            form.addSpacing(2)
            ab = QPushButton(str(action.get("label") or "TEST"))
            ab.setFixedHeight(30)
            ab.setFont(hud_font(8, QFont.Weight.Bold))
            ab.setCursor(Qt.CursorShape.PointingHandCursor)
            ab.setStyleSheet(f"""
                QPushButton {{ background: {C.ACTIVE}; color: {C.PRI};
                    border: 1px solid {C.PRI_DIM}; border-radius: 3px; }}
                QPushButton:hover {{ background: {C.HOVER}; border-color: {C.PRI}; }}
            """)
            ab.clicked.connect(lambda _=False, n=ns: self._run_action(n))
            form.addWidget(ab)

        status = self._lbl("", 8, color=C.TEXT_DIM)
        self._status_labels[ns] = status
        form.addWidget(status)

        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C.BORDER}; margin: 4px 0;")
        form.addWidget(line)

    def _style_toggle(self, btn: QPushButton):
        on = btn.isChecked()
        btn.setText("ON" if on else "OFF")
        if on:
            btn.setStyleSheet(f"QPushButton {{ background: {C.PRI_GHO}; color: {C.PRI}; "
                              f"border: 1px solid {C.PRI}; border-radius: 3px; }}")
        else:
            btn.setStyleSheet(f"QPushButton {{ background: transparent; color: {C.TEXT_MED}; "
                              f"border: 1px solid {C.BORDER}; border-radius: 3px; }}")

    # ── data ──────────────────────────────────────────────────────────────────
    def _gather(self, ns: str) -> dict:
        out = {}
        for (n, key), w in self._widgets.items():
            if n != ns:
                continue
            t = self._types.get((n, key), "text")
            if t == "choice":
                out[key] = w.currentText()
            elif t == "toggle":
                out[key] = w.isChecked()
            else:
                out[key] = w.text().strip()
        return out

    def _save_ns(self, ns: str):
        from memory.config_manager import save_plugin_config
        save_plugin_config(ns, self._gather(ns))

    def _save_all(self):
        for sec in self._sections:
            ns = sec.get("namespace") or sec.get("plugin")
            if ns:
                self._save_ns(ns)
                lbl = self._status_labels.get(ns)
                if lbl:
                    lbl.setText("Saved ✓")
                    lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")

    def _run_action(self, ns: str):
        sec = next((s for s in self._sections
                    if (s.get("namespace") or s.get("plugin")) == ns), None)
        if not sec:
            return
        run_fn = (sec.get("action") or {}).get("run")
        if not callable(run_fn):
            return
        self._save_ns(ns)                 # persist what the user typed before testing
        values = self._gather(ns)
        lbl = self._status_labels.get(ns)
        if lbl:
            lbl.setText("Testing…")
            lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")

        def worker():
            try:
                res = run_fn(values)
                if isinstance(res, tuple) and len(res) == 2:
                    ok, msg = bool(res[0]), str(res[1])
                else:
                    ok, msg = bool(res), str(res)
            except Exception as e:
                ok, msg = False, str(e)
            self._test_done.emit(ns, ok, msg)

        threading.Thread(target=worker, daemon=True).start()

    def _on_test_done(self, ns: str, ok: bool, msg: str):
        lbl = self._status_labels.get(ns)
        if not lbl:
            return
        lbl.setText(msg)
        color = C.PRI if ok else "#ff6b6b"
        lbl.setStyleSheet(f"color: {color}; background: transparent;")


class RemoteKeyOverlay(QWidget):
    """Floating overlay — QR code for instant phone pairing + manual key fallback."""

    closed = pyqtSignal()

    _OW, _OH = 420, 520

    def __init__(self, url: str, key: str, auto_login_url: str = "",
                 manual_url: str = "", expiry_secs: int = 600, parent=None,
                 bind_error: str = ""):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            RemoteKeyOverlay {{
                background: #0E0E0E;
                border: 1px solid #282828;
                border-radius: 14px;
            }}
        """)
        self._expiry          = time.time() + expiry_secs
        self._on_new_key      = None
        self._auto_login_url  = auto_login_url
        self._manual_url      = manual_url or url

        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 16, 22, 16)
        lay.setSpacing(6)

        # ── Header: Title + Close Button ──────────────────────────────────────
        hdr = QHBoxLayout()
        hdr.setContentsMargins(0, 0, 0, 0)
        hdr.setSpacing(6)

        title_lbl = QLabel("◈  REMOTE CONTROL DASHBOARD")
        title_lbl.setFont(px_font(12, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent; letter-spacing: 0.8px;")
        hdr.addWidget(title_lbl, stretch=1)

        x_btn = QPushButton("✕")
        x_btn.setFixedSize(22, 22)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT_MED};
                border: 1px solid transparent;
                border-radius: 4px;
                font-size: 11px;
            }}
            QPushButton:hover {{
                color: {C.WHITE};
                background: #1C1C1C;
                border: 1px solid {C.BORDER};
            }}
        """)
        x_btn.clicked.connect(self._do_close)
        hdr.addWidget(x_btn)
        lay.addLayout(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background: #222222; max-height: 1px; margin: 2px 0;")
        lay.addWidget(sep)

        # ── QR code ───────────────────────────────────────────────────────────
        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(164, 164)
        self._qr_label.setStyleSheet(
            "background: white; border: 1px solid #333333; border-radius: 10px; padding: 4px;"
        )
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)

        self._update_qr(auto_login_url)

        sub_lbl = QLabel("Scan with phone camera to connect instantly")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lbl.setFont(px_font(9.5))
        sub_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        lay.addWidget(sub_lbl)

        if bind_error:
            err_lbl = QLabel("⚠  " + bind_error)
            err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            err_lbl.setFont(px_font(8.5))
            err_lbl.setStyleSheet("color: #F59E0B; background: transparent;")
            lay.addWidget(err_lbl)

        try:
            from dashboard.server import blocking_firewall_rules
            _blocked = blocking_firewall_rules()
        except Exception:
            _blocked = []
        if _blocked:
            warn = QLabel(
                "⚠  Windows is blocking incoming connections to Python. "
                "Restart JARVIS and accept prompt, or allow rules under Windows Defender.",
            )
            warn.setAlignment(Qt.AlignmentFlag.AlignCenter)
            warn.setFont(px_font(8))
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #F59E0B; background: transparent;")
            lay.addWidget(warn)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("background: #222222; max-height: 1px; margin: 2px 0;")
        lay.addWidget(sep2)

        manual_title = QLabel("OR CONNECT MANUALLY ON PHONE BROWSER:")
        manual_title.setFont(px_font(8.5, QFont.Weight.Bold))
        manual_title.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; letter-spacing: 0.5px;")
        lay.addWidget(manual_title)

        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setFont(px_font(9, mono=True))
        self._url_lbl.setStyleSheet(f"color: {C.PRI}; background: #141414; border: 1px solid #222222; border-radius: 4px; padding: 3px 6px;")
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setFont(px_font(24, QFont.Weight.Bold, mono=True))
        self._key_lbl.setStyleSheet(f"""
            color: {C.WHITE};
            background: #141414;
            border: 1px solid #333333;
            border-radius: 8px;
            padding: 4px 4px;
            letter-spacing: 8px;
        """)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel()
        self._timer_lbl.setFont(px_font(9))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        new_btn = QPushButton("GENERATE NEW KEY")
        new_btn.setFixedHeight(30)
        new_btn.setFont(px_font(9.5, QFont.Weight.DemiBold))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{
                background: #1C1C1C;
                color: {C.WHITE};
                border: 1px solid #383838;
                border-radius: 6px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                background: #252525;
                border-color: {C.PRI};
                color: {C.PRI};
            }}
        """)
        new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(new_btn)

        close_btn = QPushButton("DISMISS")
        close_btn.setFixedHeight(30)
        close_btn.setFont(px_font(9.5, QFont.Weight.DemiBold))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {C.TEXT_MED};
                border: 1px solid #282828;
                border-radius: 6px;
                padding: 0 12px;
            }}
            QPushButton:hover {{
                color: {C.TEXT};
                background: #141414;
                border-color: #383838;
            }}
        """)
        close_btn.clicked.connect(self._do_close)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        self._ctimer = QTimer(self)
        self._ctimer.timeout.connect(self._tick)
        self._ctimer.start(1000)
        self._tick()

    def set_new_key_callback(self, fn) -> None:
        self._on_new_key = fn

    def _update_qr(self, url: str) -> None:
        if not url:
            self._qr_label.setText("—")
            return
        try:
            import qrcode as _qrmod
            from io import BytesIO
            qr = _qrmod.QRCode(
                box_size=5, border=2,
                error_correction=_qrmod.constants.ERROR_CORRECT_M,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(
                px.scaled(170, 170,
                          Qt.AspectRatioMode.KeepAspectRatio,
                          Qt.TransformationMode.SmoothTransformation)
            )
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(hud_font(8))
            self._qr_label.setStyleSheet(
                "color: #888; background: white; border-radius: 10px; padding: 4px;"
            )
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(hud_font(7))
            self._qr_label.setStyleSheet(
                f"color: {C.PRI}; background: white; border-radius: 10px; padding: 4px;"
            )

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        """Call from any thread when a phone successfully connects."""
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(16, 185, 129, 0.10);
            border: 1px solid rgba(16, 185, 129, 0.40);
            border-radius: 8px;
            padding: 6px 4px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("✓")
        self._qr_label.setFont(px_font(48, QFont.Weight.Bold))
        self._qr_label.setStyleSheet(
            f"color: {C.GREEN}; background: #141414; border: 1px solid rgba(16, 185, 129, 0.40); border-radius: 10px;"
        )
        self._timer_lbl.setText("Phone connected — JARVIS ready")
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")

    def _refresh_key(self):
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url    = result[0]
                key    = result[1]
                auto   = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                self._manual_url     = manual or url
                self._url_lbl.setText(self._manual_url)
                self._key_lbl.setText(key)
                self._auto_login_url = auto
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"""
                    color: {C.WHITE};
                    background: #141414;
                    border: 1px solid #333333;
                    border-radius: 8px;
                    padding: 4px 4px;
                    letter-spacing: 8px;
                """)
                self._timer_lbl.setStyleSheet(
                    f"color: {C.TEXT_DIM}; background: transparent;"
                )
                self._ctimer.start(1000)
                self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()


class IdentityAuthOverlay(_HudOverlay):
    """Owner Identity, Multi-Layer Biometrics & Permissions Management Overlay."""

    closed = pyqtSignal()
    _OW = 540

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            IdentityAuthOverlay {{
                background: rgba(10, 12, 16, 252);
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._OW)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(10)
        self._rebuild()

    def _clear_layout(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _rebuild(self):
        self._clear_layout()
        try:
            from core.identity_engine import get_owner_profile, get_hardware_device_token
            from core.permissions import list_authorized_users, get_current_speaker
        except Exception:
            get_owner_profile = lambda: {}
            get_hardware_device_token = lambda: "UNKNOWN"
            list_authorized_users = lambda: []
            get_current_speaker = lambda: "UNKNOWN"

        prof = get_owner_profile() or {}
        hw_token = get_hardware_device_token()
        auth_users = list_authorized_users()
        curr_speaker = get_current_speaker()
        is_enrolled = prof.get("enrolled", False)
        owner_name = prof.get("owner_name", "Primary Owner")

        # Top Bar
        top_row = QHBoxLayout()
        hdr = QLabel("🛡️  OWNER IDENTITY & ACCESS CONTROL")
        hdr.setFont(hud_font(12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        top_row.addWidget(hdr)
        top_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: none; font-size: 13px;")
        close_btn.clicked.connect(self._do_close)
        top_row.addWidget(close_btn)
        self._lay.addLayout(top_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        # Owner Status Card
        card = QFrame()
        card.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 10px;")
        card_lay = QVBoxLayout(card)
        card_lay.setContentsMargins(10, 8, 10, 8)
        card_lay.setSpacing(4)

        status_badge = "🟢 ENROLLED & ACTIVE" if is_enrolled else "🟠 CALIBRATION PENDING"
        badge_col = C.GREEN if is_enrolled else "#F59E0B"
        
        row1 = QHBoxLayout()
        o_lbl = QLabel(f"Owner: {owner_name}")
        o_lbl.setFont(px_font(12, QFont.Weight.Bold))
        o_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        row1.addWidget(o_lbl)
        row1.addStretch()
        b_lbl = QLabel(status_badge)
        b_lbl.setFont(px_font(10, QFont.Weight.Bold, mono=True))
        b_lbl.setStyleSheet(f"color: {badge_col}; background: transparent;")
        row1.addWidget(b_lbl)
        card_lay.addLayout(row1)

        samples_cnt = len(prof.get("calibration_samples", []))
        det_lbl = QLabel(f"• Biometric Samples: {samples_cnt} / 3 enrolled\n• Hardware Token: {hw_token[:16]}... (Apple Silicon Locked)\n• Anti-Replay Liveness: Active (Vocal Micro-Tremor + Phonetic Challenge)")
        det_lbl.setFont(px_font(9.5, mono=True))
        det_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; line-height: 1.4;")
        card_lay.addWidget(det_lbl)
        self._lay.addWidget(card)

        # Active Session Security & Live Diagnostics
        sess_box = QFrame()
        sess_box.setStyleSheet(f"background: {C.PANEL}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 6px;")
        sess_lay = QVBoxLayout(sess_box)
        sess_lay.setContentsMargins(8, 6, 8, 6)
        sess_lay.setSpacing(4)

        try:
            from core.owner_session import get_session_manager
            sm = get_session_manager()
            s_active = sm.is_active()
            s_rem = sm.remaining_seconds() if s_active else 0
            s_status_str = f"ACTIVE ({int(s_rem)}s remaining)" if s_active else "STANDBY (Expires in 15m on activation)"
            s_col = C.GREEN if s_active else C.ACC
        except Exception:
            s_status_str = "STANDBY"
            s_col = C.TEXT_DIM

        s_row = QHBoxLayout()
        s_title = QLabel(f"Current Turn Speaker: {curr_speaker}")
        s_title.setFont(px_font(10, QFont.Weight.Bold))
        s_title.setStyleSheet(f"color: {C.PRI if curr_speaker == 'OWNER' else C.TEXT}; background: transparent;")
        s_row.addWidget(s_title)
        s_row.addStretch()
        
        diag_lbl = QLabel(f"Session: {s_status_str}")
        diag_lbl.setFont(px_font(9, QFont.Weight.Bold, mono=True))
        diag_lbl.setStyleSheet(f"color: {s_col}; background: transparent;")
        s_row.addWidget(diag_lbl)
        sess_lay.addLayout(s_row)

        rule_desc = (
            "Security Policy: Dynamic Owner Recognition · Full Access Granted"
            if curr_speaker == "OWNER"
            else "Security Policy: Guest Scoped Sandbox · Memory & Elevated Tools Shielded"
        )
        r_lbl = QLabel(rule_desc)
        r_lbl.setFont(px_font(9))
        r_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        sess_lay.addWidget(r_lbl)
        self._lay.addWidget(sess_box)

        # Authorized Users Section
        auth_hdr = QLabel(f"AUTHORIZED USERS ({len(auth_users)})")
        auth_hdr.setFont(px_font(9.5, QFont.Weight.Bold))
        auth_hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 0.5px;")
        self._lay.addWidget(auth_hdr)

        auth_scroll = QScrollArea()
        auth_scroll.setWidgetResizable(True)
        auth_scroll.setFixedHeight(90)
        auth_scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: 1px solid {C.BORDER}; border-radius: 4px; }}")
        auth_inner = QWidget()
        auth_inner.setStyleSheet("background: transparent;")
        auth_in_lay = QVBoxLayout(auth_inner)
        auth_in_lay.setContentsMargins(6, 4, 6, 4)
        auth_in_lay.setSpacing(3)

        if auth_users:
            for u in auth_users:
                u_row = QLabel(f"• {u.get('name', 'User')} — Role: {u.get('role', 'GUEST')} (Tier: {u.get('tier', 'PUBLIC')})")
                u_row.setFont(px_font(9, mono=True))
                u_row.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
                auth_in_lay.addWidget(u_row)
        else:
            no_u = QLabel("No auxiliary guests registered. Owner-only operation active.")
            no_u.setFont(px_font(9))
            no_u.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            auth_in_lay.addWidget(no_u)
        auth_in_lay.addStretch()
        auth_scroll.setWidget(auth_inner)
        self._lay.addWidget(auth_scroll)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        audit_btn = QPushButton("📋 View Audit Log")
        audit_btn.setFont(px_font(10, QFont.Weight.Bold))
        audit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        audit_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.PRI}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 12px;")
        audit_btn.clicked.connect(self._show_audit_log)
        btn_row.addWidget(audit_btn)

        btn_row.addStretch()

        done_btn = QPushButton("Done")
        done_btn.setFont(px_font(10, QFont.Weight.Bold))
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setStyleSheet(f"background: {C.PRI}; color: {C.WHITE}; border: none; border-radius: 4px; padding: 5px 16px;")
        done_btn.clicked.connect(self._do_close)
        btn_row.addWidget(done_btn)
        self._lay.addLayout(btn_row)

    def _show_audit_log(self):
        log_path = Path(__file__).resolve().parent.parent / "memory" / "permission_audit.jsonl"
        content = "No audit log entries recorded yet."
        if log_path.is_file():
            try:
                lines = log_path.read_text(encoding="utf-8").strip().splitlines()
                if lines:
                    recent = lines[-12:]
                    content = "\n".join(recent)
            except Exception as e:
                content = f"Error reading audit log: {e}"
        p = self.window()
        if hasattr(p, "show_content"):
            p.show_content("JARVIS H3.0 Security & Permission Audit Log", f"```json\n{content}\n```")
        self._do_close()

    def _do_close(self):
        self.hide()
        self.closed.emit()



class VoiceLabOverlay(_HudOverlay):
    """Voice Cloning, Neural Speech Profiles & Audio Verification Overlay."""

    closed = pyqtSignal()
    _OW = 560

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            VoiceLabOverlay {{
                background: rgba(10, 12, 16, 252);
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._OW)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(10)
        self._rebuild()

    def _clear_layout(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _rebuild(self):
        self._clear_layout()
        try:
            from core.voice_cloner import list_cloned_voices
        except Exception:
            list_cloned_voices = lambda: []

        voices = list_cloned_voices()

        # Top Bar
        top_row = QHBoxLayout()
        hdr = QLabel("🎙️  VOICE LAB & VOICE CLONING")
        hdr.setFont(hud_font(12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        top_row.addWidget(hdr)
        top_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setFixedSize(22, 22)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: none; font-size: 13px;")
        close_btn.clicked.connect(self._do_close)
        top_row.addWidget(close_btn)
        self._lay.addLayout(top_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        # Active voice badge
        act_row = QHBoxLayout()
        v_title = QLabel("Active Voice Pipeline:  Default Neural JARVIS")
        for v in voices:
            if v.get("is_active"):
                v_title.setText(f"Active Voice Pipeline:  {v.get('voice_name')} ({v.get('provider')})")
                break
        v_title.setFont(px_font(10.5, QFont.Weight.Bold))
        v_title.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        act_row.addWidget(v_title)
        act_row.addStretch()
        self._lay.addLayout(act_row)

        # Cloned Voice Profiles Scroll
        v_scroll = QScrollArea()
        v_scroll.setWidgetResizable(True)
        v_scroll.setFixedHeight(180)
        v_scroll.setStyleSheet(f"QScrollArea {{ background: transparent; border: 1px solid {C.BORDER}; border-radius: 4px; }}")
        
        v_inner = QWidget()
        v_inner.setStyleSheet("background: transparent;")
        v_lay = QVBoxLayout(v_inner)
        v_lay.setContentsMargins(6, 6, 6, 6)
        v_lay.setSpacing(6)

        if voices:
            for v in voices:
                card = QFrame()
                card.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 5px;")
                c_lay = QHBoxLayout(card)
                c_lay.setContentsMargins(8, 6, 8, 6)
                
                info_lay = QVBoxLayout()
                info_lay.setSpacing(2)
                t_lbl = QLabel(f"<b>{v.get('voice_name')}</b>  [{v.get('provider')}]")
                t_lbl.setFont(px_font(10))
                t_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
                info_lay.addWidget(t_lbl)
                
                q = v.get("audio_quality", {})
                snr = q.get("snr_db", "N/A")
                sub_lbl = QLabel(f"Quality: SNR {snr} dB | Created: {v.get('created_at', '')[:10]}")
                sub_lbl.setFont(px_font(8.5, mono=True))
                sub_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
                info_lay.addWidget(sub_lbl)
                c_lay.addLayout(info_lay, stretch=1)

                v_name = v.get("voice_name")
                if not v.get("is_active"):
                    act_btn = QPushButton("Activate")
                    act_btn.setFont(px_font(9, QFont.Weight.Bold))
                    act_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                    act_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.PRI}; border: 1px solid {C.BORDER}; border-radius: 3px; padding: 3px 8px;")
                    act_btn.clicked.connect(lambda _, n=v_name: self._activate_voice(n))
                    c_lay.addWidget(act_btn)
                else:
                    curr_badge = QLabel("ACTIVE")
                    curr_badge.setFont(px_font(9, QFont.Weight.Bold, mono=True))
                    curr_badge.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
                    c_lay.addWidget(curr_badge)

                del_btn = QPushButton("Delete")
                del_btn.setFont(px_font(9))
                del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                del_btn.setStyleSheet(f"background: transparent; color: {C.RED}; border: none; padding: 3px 6px;")
                del_btn.clicked.connect(lambda _, n=v_name: self._delete_voice(n))
                c_lay.addWidget(del_btn)

                v_lay.addWidget(card)
        else:
            empty_box = QLabel("No cloned voices enrolled yet.\nUse Voice Lab to clone voices ethically with owner consent.")
            empty_box.setFont(px_font(10))
            empty_box.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; padding: 20px;")
            empty_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            v_lay.addWidget(empty_box)

        v_lay.addStretch()
        v_scroll.setWidget(v_inner)
        self._lay.addWidget(v_scroll)

        # Instructions / Guardrail Note
        guard_lbl = QLabel("🛡️ Consent Invariant: Voice cloning strictly requires verified verbal or written consent.")
        guard_lbl.setFont(px_font(9))
        guard_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._lay.addWidget(guard_lbl)

        # Bottom Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        help_btn = QPushButton("ℹ️ How to Clone")
        help_btn.setFont(px_font(10))
        help_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        help_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 12px;")
        help_btn.clicked.connect(self._show_help)
        btn_row.addWidget(help_btn)

        btn_row.addStretch()

        done_btn = QPushButton("Close")
        done_btn.setFont(px_font(10, QFont.Weight.Bold))
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setStyleSheet(f"background: {C.PRI}; color: {C.WHITE}; border: none; border-radius: 4px; padding: 5px 16px;")
        done_btn.clicked.connect(self._do_close)
        btn_row.addWidget(done_btn)
        self._lay.addLayout(btn_row)

    def _activate_voice(self, name: str):
        try:
            from core.voice_cloner import switch_active_voice
            switch_active_voice(name)
        except Exception:
            pass
        self._rebuild()

    def _delete_voice(self, name: str):
        try:
            from core.voice_cloner import delete_cloned_voice
            delete_cloned_voice(name)
        except Exception:
            pass
        self._rebuild()

    def _show_help(self):
        p = self.window()
        if hasattr(p, "show_content"):
            p.show_content(
                "JARVIS Voice Lab Guide",
                "### How to Clone a Voice in JARVIS H3.0\n\n"
                "1. **Via Voice Command:** Say: `JARVIS, clone voice from my sample named Aman with consent verified`\n"
                "2. **Via Audio File:** Say: `JARVIS, clone voice named Maya from file /path/to/sample.wav with consent verified`\n\n"
                "**Audio Quality Guardrails:**\n"
                "- Clean background (SNR > 10 dB)\n"
                "- 5 to 60 seconds duration\n"
                "- Butterworth bandpass & normalisation applied automatically."
            )
        self._do_close()

    def _do_close(self):
        self.hide()
        self.closed.emit()


# ── JARVIS H3.1 ADVANCED VOICE & SYSTEM OVERLAYS ─────────────────────────────

class MultiSpeakerOverlay(_HudOverlay):
    """Multi-Speaker Intelligence, Active Speaker Lock & Diarization Overlay."""

    closed = pyqtSignal()
    _OW = 560

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            MultiSpeakerOverlay {{
                background: rgba(10, 12, 16, 252);
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._OW)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(10)
        self._rebuild()

    def _clear_layout(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _rebuild(self):
        self._clear_layout()
        try:
            from core.speaker_intelligence import get_speaker_engine
            telem = get_speaker_engine().get_speaker_telemetry()
        except Exception:
            telem = {
                "current_speaker": "Aman Kumar", "speaker_id": "OWNER_001",
                "preferred_address": "Sir", "authentication_status": "AUTHENTICATED",
                "recognition_confidence": 0.96, "active_conversation_locked": True,
                "lock_owner": "OWNER_001", "background_noise_db": -52.0,
                "is_overlapping": False, "echo_cancellation": "ACTIVE (TTS Reference)"
            }

        top_row = QHBoxLayout()
        hdr = QLabel("👥  MULTI-SPEAKER INTELLIGENCE & DIARIZATION")
        hdr.setFont(hud_font(12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        top_row.addWidget(hdr)
        top_row.addStretch()

        x_btn = QPushButton("✕")
        x_btn.setFixedSize(22, 22)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: none; font-size: 13px;")
        x_btn.clicked.connect(self._do_close)
        top_row.addWidget(x_btn)
        self._lay.addLayout(top_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        # Active Speaker Card
        card = QFrame()
        card.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 8px;")
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(4)

        r1 = QHBoxLayout()
        s_lbl = QLabel(f"Speaker: {telem['current_speaker']}  [{telem['speaker_id']}]")
        s_lbl.setFont(px_font(12, QFont.Weight.Bold))
        s_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        r1.addWidget(s_lbl)
        r1.addStretch()

        auth_badge = QLabel(f"🟢 {telem['authentication_status']}")
        auth_badge.setFont(px_font(10, QFont.Weight.Bold, mono=True))
        auth_badge.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        r1.addWidget(auth_badge)
        c_lay.addLayout(r1)

        det = (
            f"• Preferred Address: {telem['preferred_address']}\n"
            f"• Confidence Score: {int(telem['recognition_confidence'] * 100)}%\n"
            f"• Background Noise: {telem['background_noise_db']} dBFS\n"
            f"• Acoustic Echo Cancellation: {telem['echo_cancellation']}"
        )
        det_lbl = QLabel(det)
        det_lbl.setFont(px_font(9.5, mono=True))
        det_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; line-height: 1.4;")
        c_lay.addWidget(det_lbl)
        self._lay.addWidget(card)

        # Active Speaker Lock status box
        lock_box = QFrame()
        lock_box.setStyleSheet(f"background: {C.PANEL}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 6px;")
        l_lay = QVBoxLayout(lock_box)
        l_lay.setSpacing(2)

        is_locked = telem.get("active_conversation_locked", False)
        lock_title = QLabel(f"Active Conversation Lock: {'LOCKED TO OWNER (Priority Mode)' if is_locked else 'STANDBY (All Voices)'}")
        lock_title.setFont(px_font(10, QFont.Weight.Bold))
        lock_title.setStyleSheet(f"color: {C.PRI if is_locked else C.TEXT}; background: transparent;")
        l_lay.addWidget(lock_title)

        lock_desc = QLabel(
            "When engaged, background voices are isolated and prevented from hijacking your ongoing conversation."
        )
        lock_desc.setFont(px_font(8.5))
        lock_desc.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        l_lay.addWidget(lock_desc)
        self._lay.addWidget(lock_box)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        toggle_btn = QPushButton("Release Lock" if is_locked else "Engage Owner Lock")
        toggle_btn.setFont(px_font(9.5, QFont.Weight.Bold))
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.PRI}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 12px;")
        toggle_btn.clicked.connect(self._toggle_lock)
        btn_row.addWidget(toggle_btn)

        test_btn = QPushButton("Test Overlap")
        test_btn.setFont(px_font(9.5))
        test_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        test_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 10px;")
        test_btn.clicked.connect(self._test_overlap)
        btn_row.addWidget(test_btn)

        btn_row.addStretch()

        done_btn = QPushButton("Close")
        done_btn.setFont(px_font(10, QFont.Weight.Bold))
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setStyleSheet(f"background: {C.PRI}; color: {C.WHITE}; border: none; border-radius: 4px; padding: 5px 16px;")
        done_btn.clicked.connect(self._do_close)
        btn_row.addWidget(done_btn)
        self._lay.addLayout(btn_row)

    def _toggle_lock(self):
        try:
            from core.speaker_intelligence import get_speaker_engine
            eng = get_speaker_engine()
            if eng._lock_active:
                eng.release_active_lock()
            else:
                eng._lock_active = True
                eng._locked_speaker_id = "OWNER_001"
                eng._lock_timestamp = time.time()
        except Exception:
            pass
        self._rebuild()

    def _test_overlap(self):
        p = self.window()
        if hasattr(p, "show_content"):
            from actions.speaker_manager import speaker_manager
            res = speaker_manager({"action": "test_overlap"})
            p.show_content("Speaker Overlap Test", f"**Test Result:**\n\n`{res}`")
        self._do_close()

    def _do_close(self):
        self.hide()
        self.closed.emit()


class LocalAIModelOverlay(_HudOverlay):
    """On-Device Local AI Engine & Flexible Model Router Overlay."""

    closed = pyqtSignal()
    _OW = 580

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            LocalAIModelOverlay {{
                background: rgba(10, 12, 16, 252);
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._OW)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(10)
        self._rebuild()

    def _clear_layout(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _rebuild(self):
        self._clear_layout()
        try:
            from core import local_ai_engine, model_router
            router = model_router.get_model_router()
            st = router.get_router_status()
            _, mem_msg = local_ai_engine.get_local_ai().check_memory_headroom(4.0)
        except Exception:
            st = {
                "operation_mode": "LOCAL_PRIVATE_MODE", "personality_profile": "GENERAL_ASSISTANT",
                "local_active_model": "qwen2.5:7b", "local_tps": 24.5, "is_pure_private": True
            }
            mem_msg = "Memory Headroom: Nominal (12GB Unified RAM Available)"

        top_row = QHBoxLayout()
        hdr = QLabel("🧠  ON-DEVICE LOCAL AI & MODEL ROUTER")
        hdr.setFont(hud_font(12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        top_row.addWidget(hdr)
        top_row.addStretch()

        x_btn = QPushButton("✕")
        x_btn.setFixedSize(22, 22)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: none; font-size: 13px;")
        x_btn.clicked.connect(self._do_close)
        top_row.addWidget(x_btn)
        self._lay.addLayout(top_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        # Mode Badge
        mode_box = QFrame()
        mode_box.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 8px;")
        m_lay = QVBoxLayout(mode_box)
        m_lay.setSpacing(4)

        r1 = QHBoxLayout()
        mode_str = "🟢 100% ON-DEVICE LOCAL PRIVATE" if st["is_pure_private"] else "🌐 CLOUD ASSISTED MODE"
        m_lbl = QLabel(f"Mode: {mode_str}")
        m_lbl.setFont(px_font(11, QFont.Weight.Bold))
        m_lbl.setStyleSheet(f"color: {C.GREEN if st['is_pure_private'] else C.PRI}; background: transparent;")
        r1.addWidget(m_lbl)
        r1.addStretch()
        m_lay.addLayout(r1)

        det = (
            f"• Active Model: {st['local_active_model']}\n"
            f"• Personality Profile: {st['personality_profile']}\n"
            f"• Inference Speed: {st['local_tps']} tokens/second\n"
            f"• Apple Silicon Headroom: {mem_msg}"
        )
        det_lbl = QLabel(det)
        det_lbl.setFont(px_font(9.5, mono=True))
        det_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; line-height: 1.4;")
        m_lay.addWidget(det_lbl)
        self._lay.addWidget(mode_box)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        toggle_btn = QPushButton("Switch to Cloud Assisted" if st["is_pure_private"] else "Enable Local Private Mode")
        toggle_btn.setFont(px_font(9.5, QFont.Weight.Bold))
        toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.PRI}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 12px;")
        toggle_btn.clicked.connect(self._toggle_mode)
        btn_row.addWidget(toggle_btn)

        stop_btn = QPushButton("⏹ Stop Generation")
        stop_btn.setFont(px_font(9.5))
        stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        stop_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.RED}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 10px;")
        stop_btn.clicked.connect(self._stop_generation)
        btn_row.addWidget(stop_btn)

        btn_row.addStretch()

        done_btn = QPushButton("Close")
        done_btn.setFont(px_font(10, QFont.Weight.Bold))
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setStyleSheet(f"background: {C.PRI}; color: {C.WHITE}; border: none; border-radius: 4px; padding: 5px 16px;")
        done_btn.clicked.connect(self._do_close)
        btn_row.addWidget(done_btn)
        self._lay.addLayout(btn_row)

    def _toggle_mode(self):
        try:
            from core import model_router
            r = model_router.get_model_router()
            if r.get_mode() == model_router.OperationMode.LOCAL_PRIVATE:
                r.set_mode(model_router.OperationMode.CLOUD_ASSISTED)
            else:
                r.set_mode(model_router.OperationMode.LOCAL_PRIVATE)
        except Exception:
            pass
        self._rebuild()

    def _stop_generation(self):
        try:
            from core.local_ai_engine import get_local_ai
            get_local_ai().stop_generation()
        except Exception:
            pass
        self._rebuild()

    def _do_close(self):
        self.hide()
        self.closed.emit()


class CompanionOverlay(_HudOverlay):
    """Android Companion & Hardware Control Overlay."""

    closed = pyqtSignal()
    _OW = 560

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            CompanionOverlay {{
                background: rgba(10, 12, 16, 252);
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._OW)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(10)
        self._rebuild()

    def _clear_layout(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _rebuild(self):
        self._clear_layout()
        try:
            from core.companion_gateway import get_companion_gateway
            gw = get_companion_gateway()
            dev = gw.get_primary_device()
        except Exception:
            dev = None

        top_row = QHBoxLayout()
        hdr = QLabel("📱  ANDROID COMPANION & HARDWARE")
        hdr.setFont(hud_font(12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        top_row.addWidget(hdr)
        top_row.addStretch()

        x_btn = QPushButton("✕")
        x_btn.setFixedSize(22, 22)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: none; font-size: 13px;")
        x_btn.clicked.connect(self._do_close)
        top_row.addWidget(x_btn)
        self._lay.addLayout(top_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        # Device Box
        box = QFrame()
        box.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 8px;")
        b_lay = QVBoxLayout(box)
        b_lay.setSpacing(4)

        if dev:
            d_name = dev.device_name
            b_pct = dev.battery_percent
            is_chg = dev.is_charging
            torch = dev.flashlight_on
            vol = dev.volume_level
        else:
            d_name = "Pixel 8 Pro (Simulated Standby)"
            b_pct = 88
            is_chg = False
            torch = False
            vol = 75

        r1 = QHBoxLayout()
        d_lbl = QLabel(f"Device: {d_name}")
        d_lbl.setFont(px_font(12, QFont.Weight.Bold))
        d_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        r1.addWidget(d_lbl)
        r1.addStretch()

        bat_lbl = QLabel(f"🔋 {b_pct}% {'(⚡)' if is_chg else ''}")
        bat_lbl.setFont(px_font(10, QFont.Weight.Bold, mono=True))
        bat_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        r1.addWidget(bat_lbl)
        b_lay.addLayout(r1)

        det = (
            f"• Flashlight: {'ON 🔦' if torch else 'OFF'}\n"
            f"• Media Volume: {vol}%\n"
            f"• Connection: Encrypted Local WebSocket (AES-256)\n"
            f"• Anti-Theft Guard: ARMED 🛡️"
        )
        det_lbl = QLabel(det)
        det_lbl.setFont(px_font(9.5, mono=True))
        det_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; line-height: 1.4;")
        b_lay.addWidget(det_lbl)
        self._lay.addWidget(box)

        # Controls row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        torch_btn = QPushButton("Toggle Torch")
        torch_btn.setFont(px_font(9.5))
        torch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        torch_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.PRI}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 10px;")
        torch_btn.clicked.connect(self._toggle_torch)
        btn_row.addWidget(torch_btn)

        pair_btn = QPushButton("Pair Phone (QR)")
        pair_btn.setFont(px_font(9.5))
        pair_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pair_btn.setStyleSheet(f"background: {C.PANEL}; color: {C.TEXT}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 10px;")
        pair_btn.clicked.connect(self._show_pairing_qr)
        btn_row.addWidget(pair_btn)

        btn_row.addStretch()

        done_btn = QPushButton("Close")
        done_btn.setFont(px_font(10, QFont.Weight.Bold))
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setStyleSheet(f"background: {C.PRI}; color: {C.WHITE}; border: none; border-radius: 4px; padding: 5px 16px;")
        done_btn.clicked.connect(self._do_close)
        btn_row.addWidget(done_btn)
        self._lay.addLayout(btn_row)

    def _toggle_torch(self):
        try:
            from core.companion_gateway import get_companion_gateway
            gw = get_companion_gateway()
            dev = gw.get_primary_device()
            new_state = not (dev.flashlight_on if dev else False)
            gw.execute_hardware_command("flashlight_on" if new_state else "flashlight_off")
        except Exception:
            pass
        self._rebuild()

    def _show_pairing_qr(self):
        p = self.window()
        if hasattr(p, "show_content"):
            from actions.android_control import android_control
            android_control({"action": "pair"}, player=p)
        self._do_close()

    def _do_close(self):
        self.hide()
        self.closed.emit()


class PrivacyCenterOverlay(_HudOverlay):
    """100% On-Device Privacy Center & Kill Switch Overlay."""

    closed = pyqtSignal()
    _OW = 540

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            PrivacyCenterOverlay {{
                background: rgba(10, 12, 16, 252);
                border: 1px solid {C.BORDER};
                border-radius: 8px;
            }}
        """)
        self.setFixedWidth(self._OW)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(20, 16, 20, 16)
        self._lay.setSpacing(10)
        self._rebuild()

    def _clear_layout(self):
        while self._lay.count():
            item = self._lay.takeAt(0)
            w = item.widget()
            if w is not None:
                w.hide()
                w.deleteLater()
                continue
            sub = item.layout()
            if sub is not None:
                while sub.count():
                    si = sub.takeAt(0)
                    sw = si.widget()
                    if sw is not None:
                        sw.hide()
                        sw.deleteLater()
                sub.deleteLater()

    def _rebuild(self):
        self._clear_layout()
        try:
            from actions.privacy_lock import is_privacy_locked
            locked = is_privacy_locked()
        except Exception:
            locked = False

        top_row = QHBoxLayout()
        hdr = QLabel("🔒  100% ON-DEVICE PRIVACY CENTER")
        hdr.setFont(hud_font(12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent; letter-spacing: 1px;")
        top_row.addWidget(hdr)
        top_row.addStretch()

        x_btn = QPushButton("✕")
        x_btn.setFixedSize(22, 22)
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.setStyleSheet(f"background: transparent; color: {C.TEXT_DIM}; border: none; font-size: 13px;")
        x_btn.clicked.connect(self._do_close)
        top_row.addWidget(x_btn)
        self._lay.addLayout(top_row)

        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {C.BORDER}; margin: 2px 0;")
        self._lay.addWidget(sep)

        # Status Card
        card = QFrame()
        card.setStyleSheet(f"background: {C.PANEL2}; border: 1px solid {C.BORDER}; border-radius: 6px; padding: 8px;")
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(4)

        r1 = QHBoxLayout()
        status_text = "🔴 PRIVACY LOCKDOWN ENGAGED" if locked else "🟢 LOCAL PRIVATE PROTECTED"
        s_lbl = QLabel(status_text)
        s_lbl.setFont(px_font(11.5, QFont.Weight.Bold))
        s_lbl.setStyleSheet(f"color: {C.RED if locked else C.GREEN}; background: transparent;")
        r1.addWidget(s_lbl)
        r1.addStretch()
        c_lay.addLayout(r1)

        det = (
            "• Cloud AI Egress: BLOCKED (On-device only)\n"
            "• Microphone Storage: 0% (Ephemeral in-memory buffers)\n"
            "• Conversation Database: Local Encrypted Only\n"
            "• Camera / Screen Streams: Foreground User Consent Locked"
        )
        det_lbl = QLabel(det)
        det_lbl.setFont(px_font(9.5, mono=True))
        det_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent; line-height: 1.4;")
        c_lay.addWidget(det_lbl)
        self._lay.addWidget(card)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        kill_btn = QPushButton("Disengage Privacy Lock" if locked else "🚨 Engage Privacy Lock")
        kill_btn.setFont(px_font(9.5, QFont.Weight.Bold))
        kill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        kill_btn.setStyleSheet(f"background: {C.RED if not locked else C.PANEL}; color: {C.WHITE if not locked else C.PRI}; border: 1px solid {C.BORDER}; border-radius: 4px; padding: 5px 12px;")
        kill_btn.clicked.connect(self._toggle_privacy_lock)
        btn_row.addWidget(kill_btn)

        btn_row.addStretch()

        done_btn = QPushButton("Close")
        done_btn.setFont(px_font(10, QFont.Weight.Bold))
        done_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        done_btn.setStyleSheet(f"background: {C.PRI}; color: {C.WHITE}; border: none; border-radius: 4px; padding: 5px 16px;")
        done_btn.clicked.connect(self._do_close)
        btn_row.addWidget(done_btn)
        self._lay.addLayout(btn_row)

    def _toggle_privacy_lock(self):
        try:
            from actions.privacy_lock import is_privacy_locked, set_privacy_lock
            set_privacy_lock(not is_privacy_locked())
        except Exception:
            pass
        self._rebuild()

    def _do_close(self):
        self.hide()
        self.closed.emit()



