from __future__ import annotations

# ============================================================================
#  MARK LI — modern glass UI  (drop-in replacement for the legacy cyan HUD)
#  Public contract (BASE_DIR / CONFIG_DIR / API_FILE / _read_full_config /
#  DEFAULT_UI_COLOR / apply_ui_accent / current_palette / retheme_all_widgets /
#  class JarvisUI) is byte-compatible with main.py.
#  Author: FatihMakes  ·  UI refresh 2026
# ============================================================================

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

if platform.system() == "Windows":
    _WIN_HIDE: dict = {"creationflags": 0x08000000}   # CREATE_NO_WINDOW
else:
    _WIN_HIDE: dict = {}

from PyQt6.QtCore import (
    QEasingCurve, QMimeData, QObject, QPointF, QRectF, QSize, Qt,
    QTimer, QUrl, pyqtSignal, QPropertyAnimation,
)
from PyQt6.QtGui import (
    QBrush, QColor, QConicalGradient, QDragEnterEvent, QDropEvent, QFont,
    QFontDatabase, QKeySequence, QLinearGradient, QPainter, QPainterPath,
    QPen, QPixmap, QRadialGradient, QShortcut, QIcon, QAction,
)
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QGraphicsDropShadowEffect,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea,
    QSizePolicy, QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
    QProgressBar, QGridLayout, QSpacerItem,
)


# ────────────────────────────────────────────────────────────────────────────
#  Paths / config
# ────────────────────────────────────────────────────────────────────────────
def _base_dir() -> Path:
    """Directory that holds this file (frozen exe dir when packaged)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR   = _base_dir()
CONFIG_DIR = BASE_DIR / "config"
API_FILE   = CONFIG_DIR / "api_keys.json"


def _read_full_config() -> dict:
    """Read api_keys.json. Returns {} on any error."""
    try:
        return json.loads(API_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_config(data: dict) -> None:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        API_FILE.write_text(json.dumps(data, indent=4), encoding="utf-8")
    except Exception:
        pass


_OS = platform.system()          # "Windows" | "Darwin" | "Linux"

# Window geometry
_DEFAULT_W, _DEFAULT_H = 1100, 720
_MIN_W,     _MIN_H     = 900, 600
_RAIL_W    = 64
_RIGHT_W   = 380


# ────────────────────────────────────────────────────────────────────────────
#  Fonts — Inter / Segoe UI / SF with graceful fallbacks
# ────────────────────────────────────────────────────────────────────────────
_SANS_STACK = ["Inter", "Segoe UI Variable", "Segoe UI", "SF Pro Text",
               "SF Pro Display", "Helvetica Neue", "Arial", "DejaVu Sans"]
_MONO_STACK = ["JetBrains Mono", "Cascadia Mono", "Consolas", "SF Mono",
               "Menlo", "DejaVu Sans Mono", "Courier New"]
_resolved: dict[str, str] = {}


def _pick_family(stack: list[str], fallback: str) -> str:
    key = fallback
    if key in _resolved:
        return _resolved[key]
    fam = fallback
    try:
        available = set(QFontDatabase.families())
        for name in stack:
            if name in available:
                fam = name
                break
    except Exception:
        fam = fallback
    _resolved[key] = fam
    return fam


def sans_font(size: int = 11, bold: bool = False) -> QFont:
    f = QFont(_pick_family(_SANS_STACK, "Segoe UI"), size)
    f.setWeight(QFont.Weight.DemiBold if bold else QFont.Weight.Normal)
    return f


def mono_font(size: int = 10, bold: bool = False) -> QFont:
    f = QFont(_pick_family(_MONO_STACK, "Consolas"), size)
    f.setWeight(QFont.Weight.Bold if bold else QFont.Weight.Normal)
    f.setStyleHint(QFont.StyleHint.Monospace)
    return f


def _rem(value: str, factor: float) -> str:
    """Return value*100*pct with the same suffix (used by hue-preserving tweaks)."""
    return value


# ────────────────────────────────────────────────────────────────────────────
#  Palette — dark charcoal / glass.  Accent family hue-shifts; greys desaturate.
# ────────────────────────────────────────────────────────────────────────────
class C:
    # greys (near-neutral so live hue-shift keeps the charcoal look)
    BG        = "#0a0b0d"
    PANEL     = "#121316"
    PANEL2    = "#17191d"
    GLASS     = "#1a1c21"
    DARK      = "#0d0e11"
    BORDER    = "#23262c"
    BORDER_B  = "#32363d"
    BORDER_A  = "#2a2e35"
    BAR_BG    = "#1d2025"
    # neutrals
    TEXT      = "#c7ccd4"
    TEXT_DIM  = "#6b7280"
    TEXT_MED  = "#9aa2ad"
    WHITE     = "#f0f3f7"
    # accent family (linked to ui_color)
    PRI       = "#00d4ff"
    PRI_DIM   = "#0a7d99"
    PRI_GHO   = "#0d2630"
    # fixed status colours (never hue-shifted)
    ACC       = "#ff8a3d"
    ACC2      = "#ffcc44"
    GREEN     = "#3ddc84"
    GREEN_D   = "#1f8f52"
    RED       = "#ff4d5e"
    MUTED_C   = "#ff4d6a"


_HUE_LINKED = (
    "BG", "PANEL", "PANEL2", "GLASS", "DARK", "BORDER", "BORDER_B",
    "BORDER_A", "BAR_BG", "PRI", "PRI_DIM", "PRI_GHO",
)
_PALETTE_DEFAULTS: dict[str, str] = {k: getattr(C, k) for k in _HUE_LINKED}

DEFAULT_UI_COLOR = _PALETTE_DEFAULTS["PRI"]


class _Palette(QObject):
    """Tiny signal hub so custom-painted widgets can repaint on a theme change."""
    changed = pyqtSignal()


_palette_hub = _Palette()


def apply_ui_accent(accent_hex: str) -> bool:
    """Re-derive the accent-linked palette from the chosen colour (hue shift,
    saturation preserved, greys desaturated). Returns True on success."""
    import colorsys

    accent_hex = (accent_hex or "").strip().lower()
    if not (accent_hex.startswith("#") and len(accent_hex) == 7):
        return False
    try:
        int(accent_hex[1:], 16)
    except ValueError:
        return False

    def _hsv(h: str) -> tuple[float, float, float]:
        r = int(h[1:3], 16) / 255
        g = int(h[3:5], 16) / 255
        b = int(h[5:7], 16) / 255
        return colorsys.rgb_to_hsv(r, g, b)

    base_h = _hsv(_PALETTE_DEFAULTS["PRI"])[0]
    acc_h, acc_s, _av = _hsv(accent_hex)
    dh = acc_h - base_h
    grey = acc_s < 0.08      # near-grey accent -> desaturate the whole theme

    for key, hex0 in _PALETTE_DEFAULTS.items():
        h, s, v = _hsv(hex0)
        if grey:
            s *= 0.12
        r, g, b = colorsys.hsv_to_rgb((h + dh) % 1.0, s, v)
        setattr(C, key, "#{:02x}{:02x}{:02x}".format(
            int(r * 255 + 0.5), int(g * 255 + 0.5), int(b * 255 + 0.5)))
    try:
        _palette_hub.changed.emit()
    except Exception:
        pass
    return True


def current_palette() -> dict[str, str]:
    """Snapshot of the accent-linked colours."""
    return {k: getattr(C, k) for k in _HUE_LINKED}


def retheme_all_widgets(old: dict[str, str], new: dict[str, str]) -> None:
    """Live full-theme swap: replace every old palette hex inside every widget
    stylesheet, then repaint everything (including custom-painted widgets)."""
    mapping = {old[k].lower(): new[k].lower()
               for k in old if old[k].lower() != new.get(k, old[k]).lower()}
    needed_repaint = True
    app = QApplication.instance()
    if app is None:
        return
    if mapping:
        for w in app.allWidgets():
            try:
                ss = w.styleSheet()
                if ss:
                    s2 = ss
                    for o, n in mapping.items():
                        if o in s2:
                            s2 = s2.replace(o, n)
                    if s2 != ss:
                        w.setStyleSheet(s2)
                w.update()
            except Exception:
                pass
    else:
        for w in app.allWidgets():
            try:
                w.update()
            except Exception:
                pass


def qcol(h: str, a: int = 255) -> QColor:
    c = QColor(h)
    if not c.isValid():
        c = QColor("#ffffff")
    c.setAlpha(a)
    return c


# ────────────────────────────────────────────────────────────────────────────
#  Windows GPU via NVML DLL (no subprocess, no console window)
# ────────────────────────────────────────────────────────────────────────────
_nvml_lib: object = None
_nvml_ok:  object = None


def _nvml_gpu_windows() -> float:
    """NVIDIA GPU utilisation % via nvml.dll directly — zero subprocess."""
    global _nvml_lib, _nvml_ok
    if _nvml_ok is False:
        return -1.0
    try:
        import ctypes

        class _Util(ctypes.Structure):
            _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

        if _nvml_lib is None:
            for dll_name in ("nvml", r"C:\\Windows\\System32\\nvml.dll"):
                try:
                    lib = ctypes.WinDLL(dll_name)
                    lib.nvmlInit_v2()
                    _nvml_lib = lib
                    break
                except Exception:
                    continue

        if _nvml_lib is None:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            _nvml_ok = True
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)

        dev = ctypes.c_void_p()
        _nvml_lib.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
        util = _Util()
        _nvml_lib.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(util))
        _nvml_ok = True
        return float(util.gpu)
    except Exception:
        _nvml_ok = False
        return -1.0


class _SysMetrics:
    """Background psutil/pynvml sampler. Snapshot is lock-protected."""

    def __init__(self):
        self.cpu = 0.0
        self.mem = 0.0
        self.net = 0.0
        self.gpu = -1.0
        self.tmp = -1.0
        self._lock = threading.Lock()
        self._last_net = psutil.net_io_counters()
        self._last_net_t = time.time()
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while self._running:
            try:
                self._update()
            except Exception:
                pass
            time.sleep(1.5)

    def _update(self):
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
        nc = psutil.net_io_counters()
        now = time.time()
        dt = now - self._last_net_t
        if dt > 0:
            sent = (nc.bytes_sent - self._last_net.bytes_sent) / dt
            recv = (nc.bytes_recv - self._last_net.bytes_recv) / dt
            net = (sent + recv) / (1024 * 1024)
        else:
            net = 0.0
        self._last_net = nc
        self._last_net_t = now
        gpu = self._get_gpu()
        tmp = self._get_temp()
        with self._lock:
            self.cpu, self.mem, self.net, self.gpu, self.tmp = cpu, mem, net, gpu, tmp

    def _get_gpu(self) -> float:
        try:
            import pynvml  # type: ignore
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            return float(pynvml.nvmlDeviceGetUtilizationRates(h).gpu)
        except Exception:
            pass
        if _OS == "Windows":
            return _nvml_gpu_windows()
        try:
            import ctypes
            _lib = "libnvidia-ml.so.1" if _OS == "Linux" else "libnvidia-ml.dylib"

            class _Util(ctypes.Structure):
                _fields_ = [("gpu", ctypes.c_uint), ("memory", ctypes.c_uint)]

            nv = ctypes.CDLL(_lib)
            nv.nvmlInit_v2()
            dev = ctypes.c_void_p()
            nv.nvmlDeviceGetHandleByIndex_v2(0, ctypes.byref(dev))
            u = _Util()
            nv.nvmlDeviceGetUtilizationRates(dev, ctypes.byref(u))
            return float(u.gpu)
        except Exception:
            pass
        return -1.0

    def _get_temp(self) -> float:
        try:
            temps = psutil.sensors_temperatures()
            for name in ["coretemp", "k10temp", "cpu_thermal", "acpitz",
                         "cpu-thermal", "zenpower", "it8688"]:
                if name in temps and temps[name]:
                    return temps[name][0].current
            for entries in temps.values():
                if entries:
                    return entries[0].current
        except Exception:
            pass
        if _OS == "Windows":
            try:
                import wmi  # type: ignore
                w = wmi.WMI(namespace="root/wmi")
                tz = w.MSAcpi_ThermalZoneTemperature()
                if tz:
                    return (tz[0].CurrentTemperature / 10.0) - 273.15
            except Exception:
                pass
        return -1.0

    def snapshot(self) -> dict:
        with self._lock:
            return {"cpu": self.cpu, "mem": self.mem, "net": self.net,
                    "gpu": self.gpu, "tmp": self.tmp}


_metrics = _SysMetrics()


# ────────────────────────────────────────────────────────────────────────────
#  File helpers
# ────────────────────────────────────────────────────────────────────────────
_FILE_ICONS = {
    "image": ("\U0001F5BC", "#00d4ff"), "video": ("\U0001F3AC", "#ff8a3d"),
    "audio": ("\U0001F3B5", "#c084fc"), "pdf": ("\U0001F4C4", "#ff4d5e"),
    "word": ("\U0001F4DD", "#5b9dff"), "excel": ("\U0001F4CA", "#3ddc84"),
    "code": ("\U0001F4BB", "#ffcc44"), "archive": ("\U0001F4E6", "#ff8a3d"),
    "pptx": ("\U0001F4CA", "#ff7a2f"), "text": ("\U0001F4C3", "#9aa2ad"),
    "data": ("\U0001F527", "#88ddff"), "unknown": ("\U0001F4CE", "#9aa2ad"),
}
_EXT_TO_CAT = {
    **dict.fromkeys(["jpg", "jpeg", "png", "gif", "webp", "bmp", "tiff", "svg", "ico"], "image"),
    **dict.fromkeys(["mp4", "avi", "mov", "mkv", "wmv", "flv", "webm", "m4v"], "video"),
    **dict.fromkeys(["mp3", "wav", "ogg", "m4a", "aac", "flac", "wma", "opus"], "audio"),
    **dict.fromkeys(["pdf"], "pdf"),
    **dict.fromkeys(["doc", "docx"], "word"),
    **dict.fromkeys(["xls", "xlsx", "ods"], "excel"),
    **dict.fromkeys(["ppt", "pptx"], "pptx"),
    **dict.fromkeys(["py", "js", "ts", "jsx", "tsx", "html", "css", "java", "c", "cpp",
                     "cs", "go", "rs", "rb", "php", "swift", "kt", "sh", "sql", "lua"], "code"),
    **dict.fromkeys(["zip", "rar", "tar", "gz", "7z", "bz2", "xz"], "archive"),
    **dict.fromkeys(["txt", "md", "rst", "log"], "text"),
    **dict.fromkeys(["csv", "tsv", "json", "xml"], "data"),
}


def _file_category(path: Path) -> str:
    return _EXT_TO_CAT.get(path.suffix.lower().lstrip("."), "unknown")


def _fmt_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"
    if size < 1024 ** 3:
        return f"{size / 1024 ** 2:.1f} MB"
    return f"{size / 1024 ** 3:.1f} GB"


# Status → (label, colour) mapping used by the state pill / orb.
STATE_COLORS = {
    "LISTENING":    "#3ddc84",
    "SPEAKING":     "#ff8a3d",
    "THINKING":     "#ffcc44",
    "PROCESSING":   "#ffcc44",
    "MUTED":        "#ff4d6a",
    "SLEEPING":     "#6b7280",
    "INITIALISING": "#00d4ff",
}

# ────────────────────────────────────────────────────────────────────────────
#  Custom-painted widgets — Orb, waveform, metric bars
# ────────────────────────────────────────────────────────────────────────────
class OrbWidget(QWidget):
    """Large animated orb replacing the legacy HUD rings.

    Soft radial glow · three breathing rotating gradient arcs · ripple pulses
    while speaking · particle sparkles while speaking · dims red when muted.
    An optional circular face image is drawn in the centre.
    """

    def __init__(self, face_path: str, assistant_name: str = "JARVIS", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setMinimumSize(280, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.muted = False
        self.speaking = False
        self.state = "INITIALISING"
        self._assistant_name = assistant_name

        self._tick = 0
        self._scale = 1.0
        self._tgt_scale = 1.0
        self._halo = 60.0
        self._tgt_halo = 60.0
        self._last_t = time.time()
        self._arcs = [0.0, 120.0, 240.0]
        self._pulses: list[float] = []
        self._particles: list[list[float]] = []
        self._face_px: QPixmap | None = None
        self._load_face(face_path)
        _palette_hub.changed.connect(self.update)

        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._step)
        self._tmr.start(16)          # ~60 fps

    # ── face image (circular crop, PIL if available) ────────────────────────
    def _load_face(self, path: str):
        self._face_px = None
        if not path:
            return
        p = Path(path)
        if not p.exists():
            return
        try:
            from PIL import Image, ImageDraw
            import io
            img = Image.open(str(p)).convert("RGBA")
            sz = min(img.size)
            img = img.resize((sz, sz), Image.LANCZOS)
            mk = Image.new("L", (sz, sz), 0)
            ImageDraw.Draw(mk).ellipse((2, 2, sz - 2, sz - 2), fill=255)
            img.putalpha(mk)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._face_px = px if not px.isNull() else None
        except Exception:
            # graceful fallback — no image, orb still animates
            try:
                px = QPixmap(str(p))
                self._face_px = px if not px.isNull() else None
            except Exception:
                self._face_px = None

    # ── animation step ──────────────────────────────────────────────────────
    def _step(self):
        self._tick += 1
        now = time.time()
        if now - self._last_t > (0.12 if self.speaking else 0.5):
            if self.speaking:
                self._tgt_scale = random.uniform(1.05, 1.12)
                self._tgt_halo = random.uniform(140, 190)
            elif self.muted:
                self._tgt_scale = random.uniform(0.998, 1.002)
                self._tgt_halo = random.uniform(12, 24)
            else:
                self._tgt_scale = random.uniform(1.001, 1.008)
                self._tgt_halo = random.uniform(50, 72)
            self._last_t = now

        sp = 0.35 if self.speaking else 0.12
        self._scale += (self._tgt_scale - self._scale) * sp
        self._halo += (self._tgt_halo - self._halo) * sp

        speeds = [1.6, -1.0, 2.4] if self.speaking else [0.5, -0.3, 0.85]
        for i, spd in enumerate(speeds):
            self._arcs[i] = (self._arcs[i] + spd) % 360

        fw = min(self.width(), self.height())
        lim = fw * 0.72
        spd = 5.0 if self.speaking else 2.2
        self._pulses = [r + spd for r in self._pulses if r + spd < lim]
        if len(self._pulses) < 3 and random.random() < (0.10 if self.speaking else 0.03):
            self._pulses.append(0.0)

        if self.speaking and random.random() < 0.35:
            cx, cy = self.width() / 2, self.height() / 2
            ang = random.uniform(0, 2 * math.pi)
            rs = fw * 0.26
            self._particles.append([
                cx + math.cos(ang) * rs, cy + math.sin(ang) * rs,
                math.cos(ang) * random.uniform(1.0, 2.6),
                math.sin(ang) * random.uniform(1.0, 2.6) - 0.4, 1.0,
            ])
        self._particles = [
            [p[0] + p[2], p[1] + p[3], p[2] * 0.97, p[3] * 0.97, p[4] - 0.03]
            for p in self._particles if p[4] > 0
        ]
        self.update()

    # ── painting ────────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        cx, cy = W / 2, H / 2
        fw = min(W, H)
        base_r = fw * 0.20 * self._scale

        if self.muted:
            primary = qcol("#ff4d6a")
            secondary = qcol("#7a2230")
        else:
            primary = qcol(C.PRI)
            secondary = qcol(C.PRI_DIM)

        # ── soft radial glow ─────────────────────────────────────────────────
        halo_f = max(0.02, min(1.0, self._halo / 190.0))
        glow_r = base_r * 2.6 + self._halo * 0.5
        grad = QRadialGradient(QPointF(cx, cy), glow_r)
        gc = QColor(primary)
        grad.setColorAt(0.0, qcol(gc.name(), int(150 * halo_f)))
        grad.setColorAt(0.45, qcol(secondary.name(), int(60 * halo_f)))
        grad.setColorAt(1.0, qcol(primary.name(), 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(QPointF(cx, cy), glow_r, glow_r)

        # ── ripple pulses ────────────────────────────────────────────────────
        for r in self._pulses:
            frac = max(0.0, 1.0 - r / (fw * 0.72))
            col = qcol(primary.name(), int(120 * frac))
            p.setPen(QPen(col, 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), r, r)

        # ── three breathing rotating gradient arcs ───────────────────────────
        arc_r = base_r * 1.55
        pen_w = max(2.0, fw * 0.012)
        for i, ang in enumerate(self._arcs):
            span = 90 + i * 18
            a = qcol(primary.name(), 220 - i * 45)
            b = qcol(secondary.name(), 200 - i * 45)
            try:
                g = QConicalGradient(QPointF(cx, cy), ang)
                g.setColorAt(0.0, a)
                g.setColorAt(0.5, b)
                g.setColorAt(1.0, a)
            except Exception:
                g = qcol(primary.name(), 200)
            p.setPen(QPen(QBrush(g) if isinstance(g, QConicalGradient) else g,
                          pen_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            p.setBrush(Qt.BrushStyle.NoBrush)
            rr = arc_r + i * pen_w * 1.4
            # QPainter angles are 1/16th deg, CCW from 3 o'clock
            p.drawArc(QRectF(cx - rr, cy - rr, rr * 2, rr * 2),
                      int(ang * 16), int(span * 16))

        # ── inner core ring ──────────────────────────────────────────────────
        p.setPen(QPen(qcol(primary.name(), 180), max(1.5, fw * 0.006)))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), base_r, base_r)

        # ── face image (circular) ────────────────────────────────────────────
        if self._face_px is not None:
            side = int(base_r * 1.6)
            if side > 4:
                scaled = self._face_px.scaled(
                    side, side, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation)
                p.drawPixmap(int(cx - scaled.width() / 2),
                             int(cy - scaled.height() / 2), scaled)
        else:
            core = QRadialGradient(QPointF(cx, cy), base_r)
            core.setColorAt(0.0, qcol(primary.name(), 230))
            core.setColorAt(1.0, qcol(secondary.name(), 40))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(core))
            p.drawEllipse(QPointF(cx, cy), base_r * 0.6, base_r * 0.6)

        # ── particle sparkles ────────────────────────────────────────────────
        for px_, py_, _vx, _vy, life in self._particles:
            col = qcol(primary.name(), int(200 * max(0.0, life)))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(col))
            p.drawEllipse(QPointF(px_, py_), 1.8, 1.8)


class WaveformBar(QWidget):
    """Smooth audio-style waveform strip below the orb."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.state = "INITIALISING"
        self._phase = 0.0
        self._levels = [0.0] * 64
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(33)
        _palette_hub.changed.connect(self.update)

    def _tick(self):
        self._phase += 0.28
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()
        n = len(self._levels)
        bw = max(2.0, (W - (n - 1) * 3) / n)

        if self.state == "MUTED":
            col = qcol("#ff4d6a")
            amp = 0.12
        elif self.state == "SPEAKING":
            col = qcol(C.ACC)
            amp = 1.0
        elif self.state in ("THINKING", "PROCESSING"):
            col = qcol(C.ACC2)
            amp = 0.45
        elif self.state == "SLEEPING":
            col = qcol(C.TEXT_DIM)
            amp = 0.18
        else:
            col = qcol(C.PRI)
            amp = 0.4

        for i in range(n):
            t = self._phase + i * 0.35
            if amp <= 0.2:
                h = 3.0
            else:
                h = (0.25 + 0.75 * abs(math.sin(t))) * (H - 8) * amp
            h = max(2.5, h)
            x = i * (bw + 3)
            y = (H - h) / 2.0
            a = qcol(col.name(), 90 + int(120 * amp))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(a))
            p.drawRoundedRect(QRectF(x, y, bw, h), bw / 2, bw / 2)
        # faint baseline
        p.setPen(QPen(qcol(C.BORDER, 120), 1))
        p.drawLine(0, int(H / 2), W, int(H / 2))


class StatePill(QWidget):
    """Rounded status pill: LISTENING green, SPEAKING accent, MUTED red…"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.state = "INITIALISING"
        self._pulse = 0.0
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._tick)
        self._tmr.start(50)
        _palette_hub.changed.connect(self.update)

    def _tick(self):
        self._pulse += 0.12
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        txt = self.state
        col = qcol(STATE_COLORS.get(txt, C.PRI))
        p.setFont(sans_font(10, bold=True))
        tw = p.fontMetrics().horizontalAdvance(txt)
        w = tw + 46
        h = self.height() - 4
        x = (self.width() - w) / 2.0
        y = 2.0

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol(col.name(), 30)))
        p.drawRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)
        p.setPen(QPen(qcol(col.name(), 150), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(QRectF(x, y, w, h), h / 2, h / 2)

        dot_r = 3.0 + 0.8 * abs(math.sin(self._pulse))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(col))
        p.drawEllipse(QPointF(x + 16, y + h / 2), dot_r, dot_r)

        p.setPen(QPen(col, 1))
        p.drawText(QRectF(x + 28, y, w - 34, h),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), txt)


class MetricBar(QWidget):
    """Slim rounded progress bar that shifts to amber > 65% and red > 85%."""

    def __init__(self, label: str, color: str = "", parent=None):
        super().__init__(parent)
        self.label = label
        self.color = color or C.PRI
        self.value = 0.0
        self.text = ""
        self.setFixedHeight(30)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        _palette_hub.changed.connect(self.update)

    def set_value(self, pct: float, text: str):
        self.value = max(0.0, min(100.0, float(pct)))
        self.text = text
        self.update()

    def _active_color(self) -> QColor:
        if self.label in ("NET",):
            return qcol(C.PRI)
        if self.value > 85:
            return qcol(C.RED)
        if self.value > 65:
            return qcol(C.ACC2)
        return qcol(self.color)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        W, H = self.width(), self.height()

        p.setFont(mono_font(8, bold=True))
        p.setPen(QPen(qcol(C.TEXT_MED), 1))
        p.drawText(QRectF(0, 0, 52, H),
                   int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                   self.label)

        p.setFont(mono_font(8))
        p.setPen(QPen(qcol(C.TEXT), 1))
        p.drawText(QRectF(W - 62, 0, 62, H),
                   int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                   self.text)

        bx = 54
        bw = W - 54 - 66
        by = H / 2.0 - 3.5
        bh = 7.0
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(qcol(C.BAR_BG)))
        p.drawRoundedRect(QRectF(bx, by, bw, bh), bh / 2, bh / 2)

        fw = bw * (self.value / 100.0)
        if fw > 1:
            col = self._active_color()
            grad = QLinearGradient(bx, 0, bx + bw, 0)
            grad.setColorAt(0.0, qcol(col.name(), 200))
            grad.setColorAt(1.0, col)
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(QRectF(bx, by, max(bh, fw), bh), bh / 2, bh / 2)

# ────────────────────────────────────────────────────────────────────────────
#  Chat panel — real bubbles in a scroll area
# ────────────────────────────────────────────────────────────────────────────
class ChatBubble(QWidget):
    """One chat bubble row.

    kind:
      'user'  -> right aligned, accent tinted
      'ai'    -> left aligned glass card
      'sys'   -> small centred chip
      'err'   -> small centred red chip
      'file'  -> small centred green chip
    """

    def __init__(self, text: str, kind: str = "ai", parent=None):
        super().__init__(parent)
        self.kind = kind
        row = QHBoxLayout(self)
        row.setContentsMargins(2, 2, 2, 2)
        row.setSpacing(0)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        lbl.setMaximumWidth(430)

        if kind == "user":
            lbl.setFont(sans_font(10))
            lbl.setStyleSheet(f"""
                background: {C.PRI_GHO};
                color: {C.WHITE};
                border: 1px solid {C.BORDER_B};
                border-top-right-radius: 4px;
                border-top-left-radius: 16px;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
                padding: 9px 13px;
            """)
            row.addStretch(1)
            row.addWidget(lbl, 0)
        elif kind == "ai":
            lbl.setFont(sans_font(10))
            lbl.setStyleSheet(f"""
                background: {C.PANEL2};
                color: {C.TEXT};
                border: 1px solid {C.BORDER};
                border-top-left-radius: 4px;
                border-top-right-radius: 16px;
                border-bottom-left-radius: 16px;
                border-bottom-right-radius: 16px;
                padding: 9px 13px;
            """)
            row.addWidget(lbl, 0)
            row.addStretch(1)
        else:
            color = {"err": C.RED, "file": C.GREEN}.get(kind, C.TEXT_MED)
            lbl.setFont(mono_font(8))
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"""
                background: {C.PANEL};
                color: {color};
                border: 1px solid {C.BORDER};
                border-radius: 10px;
                padding: 4px 10px;
            """)
            row.addStretch(1)
            row.addWidget(lbl, 0)
            row.addStretch(1)


class ChatPanel(QScrollArea):
    """Scrollable bubble list with smooth auto-scroll."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: transparent; width: 8px; border: none; margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: {C.BORDER_B}; border-radius: 4px; min-height: 24px;
            }}
            QScrollBar::handle:vertical:hover {{ background: {C.PRI_DIM}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0; border: none;
            }}
        """)

        self._host = QWidget()
        self._host.setStyleSheet("background: transparent;")
        self._vbox = QVBoxLayout(self._host)
        self._vbox.setContentsMargins(4, 6, 4, 6)
        self._vbox.setSpacing(6)
        self._vbox.addStretch(1)
        self.setWidget(self._host)

        self._scroll_anim = QPropertyAnimation(self.verticalScrollBar(), b"value")
        self._scroll_anim.setDuration(230)
        self._scroll_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._pending: list[str] = []
        self._typing = False
        self._tmr = QTimer(self)
        self._tmr.timeout.connect(self._next)
        self._ai_name_lc = "jarvis"

    # ── classify a prefix exactly like the legacy LogWidget did ─────────────
    def _kind_for(self, text: str) -> tuple[str, str]:
        tl = text.lower()
        if tl.startswith("you:"):
            return "user", text[4:].strip()
        if tl.startswith(f"{self._ai_name_lc}:"):
            return "ai", text.split(":", 1)[1].strip()
        if tl.startswith("jarvis:"):
            return "ai", text.split(":", 1)[1].strip()
        if tl.startswith("file:"):
            return "file", text[5:].strip()
        if tl.startswith("sys:"):
            return "sys", text[4:].strip()
        if tl.startswith("err:"):
            return "err", text[4:].strip()
        if "err" in tl:
            return "err", text.strip()
        return "ai", text.strip()

    def append_log(self, text: str):
        # Called from the Qt thread (via signal). Keep the light typewriter feel
        # by queueing a single step so long bursts animate in smoothly.
        self._pending.append(text)
        if not self._typing:
            self._next()

    def _next(self):
        if not self._pending:
            self._typing = False
            return
        self._typing = True
        text = self._pending.pop(0)
        kind, body = self._kind_for(text)
        bubble = ChatBubble(body, kind)
        self._vbox.insertWidget(self._vbox.count() - 1, bubble)
        QTimer.singleShot(10, self._scroll_to_bottom)
        if self._pending:
            self._tmr.start(25)
        else:
            self._typing = False

    def _scroll_to_bottom(self):
        sb = self.verticalScrollBar()
        self._scroll_anim.stop()
        self._scroll_anim.setStartValue(sb.value())
        self._scroll_anim.setEndValue(sb.maximum())
        self._scroll_anim.start()


class FileChip(QWidget):
    """Removable file chip shown in the composer when a file is attached."""

    removed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 0, 6, 0)
        lay.setSpacing(8)
        self._icon = QLabel("\U0001F4CE")
        self._icon.setFont(sans_font(11))
        self._icon.setStyleSheet("background: transparent;")
        lay.addWidget(self._icon)
        self._name = QLabel("")
        self._name.setFont(sans_font(9))
        self._name.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        lay.addWidget(self._name, 1)
        self._size = QLabel("")
        self._size.setFont(mono_font(8))
        self._size.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(self._size)
        x = QPushButton("\u2715")
        x.setFixedSize(20, 20)
        x.setCursor(Qt.CursorShape.PointingHandCursor)
        x.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                           border: none; border-radius: 10px; }}
            QPushButton:hover {{ color: {C.RED}; background: {C.PANEL2}; }}
        """)
        x.clicked.connect(self.removed.emit)
        lay.addWidget(x)
        self.setStyleSheet(f"""
            FileChip {{ background: {C.PANEL}; border: 1px solid {C.BORDER};
                        border-radius: 14px; }}
        """)
        self.hide()

    def set_file(self, path: str):
        p = Path(path)
        cat = _file_category(p)
        icon, _ = _FILE_ICONS.get(cat, _FILE_ICONS["unknown"])
        self._icon.setText(icon)
        try:
            size = _fmt_size(p.stat().st_size)
        except Exception:
            size = "?"
        self._name.setText(p.name)
        self._size.setText(size)
        self.show()


class Composer(QWidget):
    """Rounded composer pill: attach button + input + circular send button."""

    send_requested = pyqtSignal(str)
    attach_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Composer")
        self.setFixedHeight(52)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 6, 6, 6)
        lay.setSpacing(6)

        self.attach_btn = QPushButton("\U0001F4CE")
        self.attach_btn.setFixedSize(36, 36)
        self.attach_btn.setToolTip("Attach a file")
        self.attach_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.attach_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                           border: none; border-radius: 18px; font-size: 15px; }}
            QPushButton:hover {{ background: {C.PANEL2}; color: {C.PRI}; }}
        """)
        self.attach_btn.clicked.connect(self.attach_clicked.emit)
        lay.addWidget(self.attach_btn)

        self.input = QLineEdit()
        self.input.setPlaceholderText("Message MARK LI\u2026")
        self.input.setFont(sans_font(10))
        self.input.setStyleSheet(f"""
            QLineEdit {{ background: transparent; color: {C.WHITE};
                         border: none; padding: 2px 4px; }}
        """)
        self.input.returnPressed.connect(self._emit_send)
        lay.addWidget(self.input, 1)

        self.send_btn = QPushButton("\u25B8")
        self.send_btn.setFixedSize(38, 38)
        self.send_btn.setToolTip("Send (Enter)")
        self.send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_btn.setStyleSheet(f"""
            QPushButton {{ background: {C.PRI}; color: #04060a;
                           border: none; border-radius: 19px;
                           font-size: 16px; font-weight: bold; }}
            QPushButton:hover {{ background: {C.WHITE}; }}
            QPushButton:pressed {{ background: {C.PRI_DIM}; }}
        """)
        self.send_btn.clicked.connect(self._emit_send)
        lay.addWidget(self.send_btn)

        self.setStyleSheet(f"""
            Composer {{ background: {C.GLASS}; border: 1px solid {C.BORDER};
                        border-radius: 24px; }}
            Composer:focus-within {{ border: 1px solid {C.PRI_DIM}; }}
        """)

    def _emit_send(self):
        txt = self.input.text().strip()
        if not txt:
            return
        self.input.clear()
        self.send_requested.emit(txt)


# ────────────────────────────────────────────────────────────────────────────
#  Content panel — slide-up card
# ────────────────────────────────────────────────────────────────────────────
class ContentPanel(QWidget):
    """Slide-up card shown over the bottom of the orb area by show_content()."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ContentPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet(f"""
            QWidget#ContentPanel {{
                background: {C.PANEL};
                border: 1px solid {C.BORDER_B};
                border-radius: 16px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 14)
        lay.setSpacing(8)

        hdr = QHBoxLayout()
        hdr.setSpacing(10)
        self.title_lbl = QLabel("BRIEFING")
        self.title_lbl.setFont(sans_font(11, bold=True))
        self.title_lbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(self.title_lbl)
        hdr.addStretch()
        self.ts_lbl = QLabel("")
        self.ts_lbl.setFont(mono_font(8))
        self.ts_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        hdr.addWidget(self.ts_lbl)
        dismiss = QPushButton("DISMISS")
        dismiss.setFixedHeight(24)
        dismiss.setCursor(Qt.CursorShape.PointingHandCursor)
        dismiss.setFont(sans_font(8, bold=True))
        dismiss.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                           border: 1px solid {C.BORDER}; border-radius: 12px;
                           padding: 0 12px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}
        """)
        dismiss.clicked.connect(self.hide)
        hdr.addWidget(dismiss)
        lay.addLayout(hdr)

        self.body = QTextEdit()
        self.body.setReadOnly(True)
        self.body.setFont(sans_font(9))
        self.body.setStyleSheet(f"""
            QTextEdit {{ background: {C.DARK}; color: {C.TEXT};
                         border: 1px solid {C.BORDER}; border-radius: 12px;
                         padding: 10px; selection-background-color: {C.PRI_GHO}; }}
            QScrollBar:vertical {{ background: transparent; width: 8px; border: none; }}
            QScrollBar::handle:vertical {{ background: {C.BORDER_B};
                                           border-radius: 4px; min-height: 20px; }}
        """)
        lay.addWidget(self.body, 1)
        self.hide()

        self._anim = QPropertyAnimation(self, b"geometry")
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def present(self, title: str, text: str) -> None:
        self.title_lbl.setText(title.upper()[:48])
        self.ts_lbl.setText(time.strftime("%H:%M"))
        self.body.setPlainText(text)
        self.body.moveCursor(self.body.textCursor().MoveOperation.Start)
        self._slide_up()

    def _target_rect(self) -> QRectF:
        """Slide-up card target rect, anchored in the centre orb area and
        clamped so it always lies fully inside the central widget."""
        win = self.window()
        if win is not None and hasattr(win, "content_card_rect"):
            try:
                r = win.content_card_rect()
                if r is not None and r.width() > 0 and r.height() > 0:
                    return QRectF(r)
            except Exception:
                pass
        par = self.parentWidget()
        W = par.width() if par is not None else 600
        H = par.height() if par is not None else 400
        margin = 16
        card_h = min(260, max(120, H - 2 * margin))
        return QRectF(margin, max(0, H - card_h - margin),
                      max(80, W - 2 * margin), card_h)

    def _slide_up(self):
        par = self.parentWidget()
        end = self._target_rect()
        H = par.height() if par is not None else int(end.y() + end.height() + 16)
        start = QRectF(end.x(), H + 8, end.width(), end.height())
        self.setGeometry(start.toRect())
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()

# ────────────────────────────────────────────────────────────────────────────
#  Overlay base + hidden dim backdrop
# ────────────────────────────────────────────────────────────────────────────
class DimBackdrop(QWidget):
    """Semi-transparent dim layer shown behind modal overlays."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("background: rgba(0,0,0,150);")
        self.hide()

    def mousePressEvent(self, e):
        # swallow clicks so the app behind isn't reached
        e.accept()


class OverlayCard(QWidget):
    """Base rounded glass card for all overlays."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

    def _card_qss(self) -> str:
        return f"""
            {self.__class__.__name__} {{
                background: rgba(16, 18, 22, 250);
                border: 1px solid {C.BORDER_B};
                border-radius: 18px;
            }}
        """


# ────────────────────────────────────────────────────────────────────────────
#  Setup overlay — API key + OS selector
# ────────────────────────────────────────────────────────────────────────────
class SetupOverlay(OverlayCard):
    done = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self._card_qss())

        detected = {"darwin": "mac", "windows": "windows"}.get(_OS.lower(), "linux")
        self._sel_os = detected

        lay = QVBoxLayout(self)
        lay.setContentsMargins(30, 26, 30, 26)
        lay.setSpacing(10)

        def _lbl(txt, size=10, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(sans_font(size, bold))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        lay.addWidget(_lbl("Set up MARK LI", 16, True))
        lay.addWidget(_lbl("One-time configuration before first boot.", 10, color=C.TEXT_DIM))
        lay.addSpacing(6)

        lay.addWidget(_lbl("GEMINI API KEY", 9, color=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_input.setPlaceholderText("AIza\u2026")
        self._key_input.setFont(mono_font(10))
        self._key_input.setFixedHeight(36)
        self._key_stylesheet = f"""
            QLineEdit {{ background: {C.DARK}; color: {C.WHITE};
                         border: 1px solid {C.BORDER}; border-radius: 12px;
                         padding: 6px 12px; }}
            QLineEdit:focus {{ border: 1px solid {C.PRI}; }}
        """
        self._key_input.setStyleSheet(self._key_stylesheet)
        lay.addWidget(self._key_input)
        lay.addSpacing(6)

        lay.addWidget(_lbl("OPERATING SYSTEM", 9, color=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))
        det_name = {"windows": "Windows", "mac": "macOS", "linux": "Linux"}[detected]
        lay.addWidget(_lbl(f"Auto-detected: {det_name}", 9, color=C.ACC2, align=Qt.AlignmentFlag.AlignLeft))

        os_row = QHBoxLayout()
        os_row.setSpacing(8)
        self._os_btns: dict[str, QPushButton] = {}
        for key, label in [("windows", "Windows"), ("mac", "macOS"), ("linux", "Linux")]:
            btn = QPushButton(label)
            btn.setFont(sans_font(10, bold=True))
            btn.setFixedHeight(36)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _, k=key: self._sel(k))
            os_row.addWidget(btn)
            self._os_btns[key] = btn
        lay.addLayout(os_row)
        self._sel(detected)
        lay.addSpacing(10)

        init_btn = QPushButton("INITIALISE")
        init_btn.setFont(sans_font(11, bold=True))
        init_btn.setFixedHeight(42)
        init_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        init_btn.setStyleSheet(f"""
            QPushButton {{ background: {C.PRI}; color: #04060a; border: none;
                           border-radius: 14px; }}
            QPushButton:hover {{ background: {C.WHITE}; }}
            QPushButton:pressed {{ background: {C.PRI_DIM}; }}
        """)
        init_btn.clicked.connect(self._submit)
        lay.addWidget(init_btn)

    def _sel(self, key: str):
        self._sel_os = key
        pal = {"windows": (C.PRI, "#04060a"), "mac": (C.ACC2, "#1a1400"),
               "linux": (C.GREEN, "#001a0d")}
        for k, btn in self._os_btns.items():
            if k == key:
                fg, bg = pal[k]
                btn.setStyleSheet(f"""
                    QPushButton {{ background: {fg}; color: {bg};
                                   border: none; border-radius: 12px;
                                   font-weight: bold; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{ background: {C.DARK}; color: {C.TEXT_DIM};
                                   border: 1px solid {C.BORDER}; border-radius: 12px; }}
                    QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
                """)

    def _submit(self):
        key = self._key_input.text().strip()
        if not key:
            self._key_input.setStyleSheet(
                self._key_stylesheet +
                f" QLineEdit {{ border: 1px solid {C.RED}; }}")
            return
        self.done.emit(key, self._sel_os)


# ────────────────────────────────────────────────────────────────────────────
#  Hue wheel + customise overlay
# ────────────────────────────────────────────────────────────────────────────
class HueWheel(QWidget):
    """Circular hue-wheel colour picker with a draggable handle."""

    hue_picked = pyqtSignal(str)
    hue_committed = pyqtSignal(str)
    _RING = 18

    def __init__(self, initial_hex: str = DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setFixedSize(150, 150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hue = 0.53
        self._drag = False
        self.set_color(initial_hex)

    def color(self) -> str:
        return QColor.fromHsvF(self._hue, 1.0, 1.0).name()

    def set_color(self, hex_str: str):
        c = QColor((hex_str or "").strip())
        if c.isValid() and c.hsvHueF() >= 0:
            self._hue = c.hsvHueF()
            self.update()

    def _ring_rect(self) -> QRectF:
        m = self._RING / 2 + 3
        return QRectF(self.rect()).adjusted(m, m, -m, -m)

    def _hue_from_pos(self, pos: QPointF) -> float:
        c = QRectF(self.rect()).center()
        dx = pos.x() - c.x()
        dy = c.y() - pos.y()
        return (math.atan2(dy, dx) / (2 * math.pi)) % 1.0

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self._ring_rect()
        center = rect.center()
        grad = QConicalGradient(center, 0)
        for i in range(0, 361, 20):
            grad.setColorAt(i / 360.0, QColor.fromHsvF((i % 360) / 360.0, 1.0, 1.0))
        p.setPen(QPen(QBrush(grad), self._RING))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(rect)

        preview = QColor.fromHsvF(self._hue, 1.0, 1.0)
        inner = rect.adjusted(32, 32, -32, -32)
        p.setPen(QPen(qcol(C.BORDER_B), 1))
        p.setBrush(QBrush(preview))
        p.drawEllipse(inner)

        r = rect.width() / 2
        ang = self._hue * 2 * math.pi
        hx = center.x() + r * math.cos(ang)
        hy = center.y() - r * math.sin(ang)
        p.setPen(QPen(QColor("#0a0b0d"), 2))
        p.setBrush(QBrush(QColor("#ffffff")))
        p.drawEllipse(QPointF(hx, hy), 8.0, 8.0)

    def mousePressEvent(self, e):
        self._drag = True
        self._hue = self._hue_from_pos(e.position())
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


class CustomizeOverlay(OverlayCard):
    saved = pyqtSignal(str, str, str)   # assistant_name, user_name, ui_color
    _OW, _OH = 420, 560

    def __init__(self, assistant_name="JARVIS", user_name="",
                 ui_color=DEFAULT_UI_COLOR, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self._card_qss())
        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 22, 26, 22)
        lay.setSpacing(9)

        def _lbl(txt, size=10, bold=False, color=C.PRI, align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(sans_font(size, bold))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            return w

        fs = (f"QLineEdit {{ background: {C.DARK}; color: {C.WHITE}; "
              f"border: 1px solid {C.BORDER}; border-radius: 12px; padding: 6px 12px; }}"
              f"QLineEdit:focus {{ border: 1px solid {C.PRI}; }}")

        lay.addWidget(_lbl("Customise assistant", 15, True))

        lay.addWidget(_lbl("ASSISTANT NAME", 9, color=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))
        self._name_input = QLineEdit(assistant_name)
        self._name_input.setFont(sans_font(11))
        self._name_input.setFixedHeight(36)
        self._name_input.setStyleSheet(fs)
        lay.addWidget(self._name_input)

        lay.addWidget(_lbl("YOUR NAME", 9, color=C.TEXT_MED, align=Qt.AlignmentFlag.AlignLeft))
        self._user_input = QLineEdit(user_name)
        self._user_input.setPlaceholderText("e.g. Tony")
        self._user_input.setFont(sans_font(11))
        self._user_input.setFixedHeight(36)
        self._user_input.setStyleSheet(fs)
        lay.addWidget(self._user_input)

        clr_hdr = QHBoxLayout()
        clr_hdr.addWidget(_lbl("ACCENT COLOUR", 9, color=C.TEXT_MED,
                               align=Qt.AlignmentFlag.AlignLeft))
        clr_hdr.addStretch()
        df_btn = QPushButton("DEFAULT")
        df_btn.setFixedSize(78, 24)
        df_btn.setFont(sans_font(8, bold=True))
        df_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        df_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                           border: 1px solid {C.BORDER}; border-radius: 12px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}
        """)
        df_btn.clicked.connect(lambda: self._set_color(DEFAULT_UI_COLOR))
        clr_hdr.addWidget(df_btn)
        lay.addLayout(clr_hdr)

        self._initial_color = (ui_color or DEFAULT_UI_COLOR).strip().lower()
        self._sel_color = self._initial_color
        self.on_preview = None

        self._wheel = HueWheel(self._sel_color)
        wheel_row = QHBoxLayout()
        wheel_row.addStretch()
        wheel_row.addWidget(self._wheel)
        wheel_row.addStretch()
        lay.addLayout(wheel_row)
        self._wheel.hue_picked.connect(self._on_wheel_pick)
        self._wheel.hue_committed.connect(self._on_wheel_commit)

        self._hex_input = QLineEdit(self._sel_color)
        self._hex_input.setPlaceholderText("#00d4ff")
        self._hex_input.setFont(mono_font(11))
        self._hex_input.setFixedHeight(32)
        self._hex_input.setStyleSheet(fs)
        self._hex_input.textEdited.connect(self._on_hex_edited)
        lay.addWidget(self._hex_input)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        save_btn = QPushButton("APPLY")
        save_btn.setFixedHeight(40)
        save_btn.setFont(sans_font(11, bold=True))
        save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        save_btn.setStyleSheet(f"""
            QPushButton {{ background: {C.PRI}; color: #04060a; border: none;
                           border-radius: 14px; }}
            QPushButton:hover {{ background: {C.WHITE}; }}
        """)
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("CANCEL")
        cancel_btn.setFixedHeight(40)
        cancel_btn.setFont(sans_font(11))
        cancel_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                           border: 1px solid {C.BORDER}; border-radius: 14px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}
        """)
        cancel_btn.clicked.connect(self._cancel)
        btn_row.addWidget(cancel_btn)
        lay.addLayout(btn_row)

    def _set_color(self, hx: str, update_wheel: bool = True, preview: bool = True):
        self._sel_color = hx.strip().lower()
        self._hex_input.blockSignals(True)
        self._hex_input.setText(self._sel_color)
        self._hex_input.blockSignals(False)
        if update_wheel:
            self._wheel.set_color(self._sel_color)
        if preview and self.on_preview:
            self.on_preview(self._sel_color)

    def _on_wheel_pick(self, hx: str):
        self._sel_color = hx
        self._hex_input.blockSignals(True)
        self._hex_input.setText(hx)
        self._hex_input.blockSignals(False)

    def _on_wheel_commit(self, hx: str):
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
        if self.on_preview and self._sel_color != self._initial_color:
            self.on_preview(self._initial_color)
        self.hide()

    def _save(self):
        name = self._name_input.text().strip() or "JARVIS"
        user = self._user_input.text().strip()
        self.saved.emit(name, user, self._sel_color or DEFAULT_UI_COLOR)
        self.hide()


# ────────────────────────────────────────────────────────────────────────────
#  Plugin manager overlay
# ────────────────────────────────────────────────────────────────────────────
class PluginManagerOverlay(OverlayCard):
    _OW = 440

    def __init__(self, plugins: list[dict], parent=None):
        super().__init__(parent)
        self.setStyleSheet(self._card_qss())
        self.setFixedWidth(self._OW)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(8)

        hdr = QLabel("Plugins")
        hdr.setFont(sans_font(15, bold=True))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)

        if not plugins:
            empty = QLabel("No plugins found in /plugins.")
            empty.setFont(sans_font(10))
            empty.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
            lay.addWidget(empty)

        for p in plugins:
            lay.addLayout(self._build_row(p))

        close_btn = QPushButton("CLOSE")
        close_btn.setFixedHeight(36)
        close_btn.setFont(sans_font(10))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                           border: 1px solid {C.BORDER}; border-radius: 14px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}
        """)
        close_btn.clicked.connect(self.hide)
        lay.addWidget(close_btn)
        self.adjustSize()

    def _build_row(self, p: dict) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        valid = bool(p.get("valid", True))
        name = p.get("name", "plugin")
        label_text = name if valid else f"{name}  (broken)"
        lbl = QLabel(label_text)
        lbl.setFont(sans_font(10))
        lbl.setStyleSheet(f"color: {C.TEXT if valid else C.TEXT_DIM}; background: transparent;")
        lbl.setToolTip(p.get("description", "") if valid else p.get("error", ""))
        row.addWidget(lbl, 1)

        btn = QPushButton()
        btn.setFixedSize(76, 28)
        btn.setFont(sans_font(9, bold=True))
        if not valid:
            btn.setText("BROKEN")
            btn.setEnabled(False)
            btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                               border: 1px solid {C.BORDER}; border-radius: 12px; }}
            """)
        else:
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._style_toggle(btn, bool(p.get("enabled", False)))
            btn.clicked.connect(lambda _, n=name, b=btn: self._toggle(n, b))
        row.addWidget(btn)
        return row

    def _style_toggle(self, btn: QPushButton, enabled: bool):
        if enabled:
            btn.setText("ON")
            btn.setStyleSheet(f"""
                QPushButton {{ background: {C.GREEN_D}; color: {C.WHITE};
                               border: none; border-radius: 12px; }}
                QPushButton:hover {{ background: {C.GREEN}; color: #04060a; }}
            """)
        else:
            btn.setText("OFF")
            btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                               border: 1px solid {C.BORDER}; border-radius: 12px; }}
                QPushButton:hover {{ color: {C.TEXT}; border-color: {C.BORDER_B}; }}
            """)

    def _toggle(self, name: str, btn: QPushButton):
        from memory.config_manager import get_plugin_enabled, save_plugin_enabled
        new_val = not get_plugin_enabled(name)
        save_plugin_enabled(name, new_val)
        self._style_toggle(btn, new_val)

# ────────────────────────────────────────────────────────────────────────────
#  Remote key overlay — QR + manual key + expiry countdown
# ────────────────────────────────────────────────────────────────────────────
class RemoteKeyOverlay(OverlayCard):
    closed = pyqtSignal()
    _OW, _OH = 420, 500

    def __init__(self, url: str, key: str, auto_login_url: str = "",
                 manual_url: str = "", expiry_secs: int = 600, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self._card_qss())
        self._expiry = time.time() + expiry_secs
        self._on_new_key = None
        self._auto_login_url = auto_login_url
        self._manual_url = manual_url or url

        lay = QVBoxLayout(self)
        lay.setContentsMargins(26, 20, 26, 20)
        lay.setSpacing(8)

        def _lbl(txt, size=10, bold=False, color=C.PRI,
                 align=Qt.AlignmentFlag.AlignCenter):
            w = QLabel(txt)
            w.setAlignment(align)
            w.setFont(sans_font(size, bold))
            w.setStyleSheet(f"color: {color}; background: transparent;")
            w.setWordWrap(True)
            return w

        lay.addWidget(_lbl("Remote access", 15, True))

        self._qr_label = QLabel()
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setFixedSize(184, 184)
        self._qr_label.setStyleSheet(
            "background: white; border-radius: 14px; padding: 6px;")
        qr_row = QHBoxLayout()
        qr_row.addStretch()
        qr_row.addWidget(self._qr_label)
        qr_row.addStretch()
        lay.addLayout(qr_row)
        self._update_qr(auto_login_url)

        lay.addWidget(_lbl("Scan with your phone camera to connect", 9, color=C.TEXT_DIM))

        lay.addWidget(_lbl("Or enter manually", 9, color=C.TEXT_DIM,
                           align=Qt.AlignmentFlag.AlignLeft))
        self._url_lbl = QLabel(self._manual_url)
        self._url_lbl.setFont(mono_font(9))
        self._url_lbl.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        self._url_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self._url_lbl)

        self._key_lbl = QLabel(key)
        self._key_lbl.setFont(mono_font(24, bold=True))
        self._key_lbl.setStyleSheet(f"""
            color: {C.ACC};
            background: {C.PANEL2};
            border: 1px solid {C.BORDER_B};
            border-radius: 14px;
            padding: 8px 6px;
            letter-spacing: 12px;
        """)
        self._key_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._key_lbl)

        self._timer_lbl = QLabel()
        self._timer_lbl.setFont(mono_font(9))
        self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        self._timer_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._timer_lbl)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        new_btn = QPushButton("NEW KEY")
        new_btn.setFixedHeight(38)
        new_btn.setFont(sans_font(10, bold=True))
        new_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_btn.setStyleSheet(f"""
            QPushButton {{ background: {C.PRI}; color: #04060a; border: none;
                           border-radius: 14px; }}
            QPushButton:hover {{ background: {C.WHITE}; }}
        """)
        new_btn.clicked.connect(self._refresh_key)
        btn_row.addWidget(new_btn)

        close_btn = QPushButton("DISMISS")
        close_btn.setFixedHeight(38)
        close_btn.setFont(sans_font(10))
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                           border: 1px solid {C.BORDER}; border-radius: 14px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}
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
            self._qr_label.setText("\u2014")
            return
        try:
            import qrcode as _qrmod
            from io import BytesIO
            qr = _qrmod.QRCode(box_size=5, border=2,
                               error_correction=_qrmod.constants.ERROR_CORRECT_M)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = BytesIO()
            img.save(buf, format="PNG")
            px = QPixmap()
            px.loadFromData(buf.getvalue())
            self._qr_label.setPixmap(px.scaled(
                172, 172, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        except ImportError:
            self._qr_label.setText("pip install\nqrcode[pil]")
            self._qr_label.setFont(mono_font(9))
            self._qr_label.setStyleSheet(
                "color: #666; background: white; border-radius: 14px; padding: 6px;")
        except Exception:
            self._qr_label.setText(url[:28])
            self._qr_label.setFont(mono_font(8))
            self._qr_label.setStyleSheet(
                f"color: {C.PRI}; background: white; border-radius: 14px; padding: 6px;")

    def _tick(self):
        remaining = max(0, int(self._expiry - time.time()))
        m, s = divmod(remaining, 60)
        self._timer_lbl.setText(f"Key expires in  {m:02d}:{s:02d}")
        if remaining == 0:
            self._do_close()

    def mark_connected(self) -> None:
        self._ctimer.stop()
        self._key_lbl.setText("CONNECTED")
        self._key_lbl.setStyleSheet(f"""
            color: {C.GREEN};
            background: rgba(61,220,132,0.08);
            border: 2px solid rgba(61,220,132,0.4);
            border-radius: 14px;
            padding: 8px 6px;
            letter-spacing: 4px;
        """)
        self._qr_label.setText("\u2713")
        self._qr_label.setFont(sans_font(48, bold=True))
        self._qr_label.setStyleSheet(
            f"color: {C.GREEN}; background: {C.PANEL2}; border-radius: 14px;")
        self._timer_lbl.setText("Phone connected \u2014 ready")
        self._timer_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")

    def _refresh_key(self):
        if self._on_new_key:
            result = self._on_new_key()
            if result:
                url = result[0]
                key = result[1]
                auto = result[2] if len(result) >= 3 else ""
                manual = result[3] if len(result) >= 4 else url
                self._manual_url = manual or url
                self._url_lbl.setText(self._manual_url)
                self._key_lbl.setText(key)
                self._auto_login_url = auto
                self._update_qr(auto or url)
                self._expiry = time.time() + 600
                self._key_lbl.setStyleSheet(f"""
                    color: {C.ACC};
                    background: {C.PANEL2};
                    border: 1px solid {C.BORDER_B};
                    border-radius: 14px;
                    padding: 8px 6px;
                    letter-spacing: 12px;
                """)
                self._timer_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
                self._ctimer.start(1000)
                self._tick()

    def _do_close(self):
        self._ctimer.stop()
        self.hide()
        self.closed.emit()


# ────────────────────────────────────────────────────────────────────────────
#  Clipboard panel — floating quick actions on copy
# ────────────────────────────────────────────────────────────────────────────
class ClipboardPanel(OverlayCard):
    action_requested = pyqtSignal(str)
    _W, _H = 340, 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self._card_qss())
        self.setFixedWidth(self._W)
        self._clip_text = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 12)
        lay.setSpacing(8)

        hdr = QHBoxLayout()
        icon_lbl = QLabel("Clipboard detected")
        icon_lbl.setFont(sans_font(9, bold=True))
        icon_lbl.setStyleSheet(f"color: {C.ACC2}; background: transparent;")
        hdr.addWidget(icon_lbl)
        hdr.addStretch()
        x_btn = QPushButton("\u2715")
        x_btn.setFixedSize(20, 20)
        x_btn.setFont(sans_font(9))
        x_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        x_btn.clicked.connect(self.hide)
        hdr.addWidget(x_btn)
        lay.addLayout(hdr)

        self._preview = QLabel()
        self._preview.setFont(sans_font(9))
        self._preview.setStyleSheet(f"""
            color: {C.TEXT}; background: {C.PANEL};
            border: 1px solid {C.BORDER}; border-radius: 10px;
            padding: 6px 10px;
        """)
        self._preview.setFixedHeight(34)
        lay.addWidget(self._preview)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)
        _bs = (f"QPushButton {{ background: {C.PANEL}; color: {C.TEXT_MED}; "
               f"border: 1px solid {C.BORDER}; border-radius: 11px; padding: 0 8px; }}"
               f"QPushButton:hover {{ color: {C.PRI}; border-color: {C.PRI_DIM}; }}")
        for label, cmd_fmt in [
            ("TRANSLATE", "Translate this text to English: {text}"),
            ("SUMMARISE", "Summarise this: {text}"),
            ("EXPLAIN", "Explain this: {text}"),
            ("FIX", "Fix grammar and spelling: {text}"),
        ]:
            b = QPushButton(label)
            b.setFixedHeight(26)
            b.setFont(sans_font(8, bold=True))
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
        preview = text[:58].replace("\n", " ")
        if len(text) > 58:
            preview += "\u2026"
        self._preview.setText(f'"{preview}"')
        self.show()
        self.raise_()
        self._dismiss_timer.start(8000)


# ────────────────────────────────────────────────────────────────────────────
#  Camera still preview overlay (auto dismiss 6s)
# ────────────────────────────────────────────────────────────────────────────
class CameraPreview(OverlayCard):
    _W, _H = 264, 208

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self._card_qss())
        self.setFixedWidth(self._W)
        self._frame: QPixmap | None = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(10, 8, 10, 10)
        lay.setSpacing(6)

        hdr = QHBoxLayout()
        title = QLabel("Visual input")
        title.setFont(sans_font(9, bold=True))
        title.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        hdr.addWidget(title)
        hdr.addStretch()
        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(20, 20)
        close_btn.setFont(sans_font(9))
        close_btn.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent; border: none;")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        hdr.addWidget(close_btn)
        lay.addLayout(hdr)

        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet("background: transparent;")
        lay.addWidget(self._img_lbl, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)
        self.hide()

    def show_frame(self, img_bytes: bytes) -> None:
        px = QPixmap()
        px.loadFromData(img_bytes)
        if not px.isNull():
            self._frame = px
            self._render()
        self.show()
        self.raise_()
        self._timer.start(6_000)

    def _render(self):
        if self._frame is None:
            return
        max_w = self._W - 24
        scaled = self._frame.scaled(
            max_w, 170, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._img_lbl.setPixmap(scaled)
        self._img_lbl.setFixedSize(scaled.width(), scaled.height())
        self.adjustSize()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._render()

# ────────────────────────────────────────────────────────────────────────────
#  Drop-zone shim so JarvisUI.current_file keeps working
# ────────────────────────────────────────────────────────────────────────────
class _DropZoneShim:
    def __init__(self, win: "MainWindow"):
        self._win = win

    def current_file(self) -> str | None:
        return self._win._current_file

    def clear_file(self):
        self._win._clear_file()


# ────────────────────────────────────────────────────────────────────────────
#  Main window
# ────────────────────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    _log_sig        = pyqtSignal(str)
    _state_sig      = pyqtSignal(str)
    _content_sig    = pyqtSignal(str, str)
    _reconfig_sig   = pyqtSignal()
    _camera_sig     = pyqtSignal(bytes)
    _cam_stream_sig = pyqtSignal(bool)
    _cam_frame_sig  = pyqtSignal(bytes)
    _clipboard_sig  = pyqtSignal(str)

    def __init__(self, face_path: str):
        super().__init__()
        self._face_path = face_path

        cfg = _read_full_config()
        self._assistant_name = (cfg.get("assistant_name") or "JARVIS").strip()
        display = self._assistant_name.upper()

        _ui_color = (cfg.get("ui_color") or "").strip()
        if _ui_color and _ui_color.lower() != DEFAULT_UI_COLOR:
            apply_ui_accent(_ui_color)

        self.setWindowTitle(f"{display} — MARK LI")
        self.setMinimumSize(_MIN_W, _MIN_H)
        self.resize(_DEFAULT_W, _DEFAULT_H)
        try:
            scr = QApplication.primaryScreen().availableGeometry()
            self.move((scr.width() - _DEFAULT_W) // 2, (scr.height() - _DEFAULT_H) // 2)
        except Exception:
            pass

        # main.py-injected callables / state
        self.on_text_command = None
        self.on_remote_clicked = None
        self.on_interrupt = None
        self.get_plugins = None
        self._muted = False
        self._current_file: str | None = None
        self._remote_overlay: RemoteKeyOverlay | None = None
        self._customize_overlay: CustomizeOverlay | None = None
        self._plugin_manager_overlay = None
        self._overlay: SetupOverlay | None = None
        self._drop_zone = _DropZoneShim(self)

        self.setAcceptDrops(True)
        self.setStyleSheet(f"QMainWindow {{ background: {C.BG}; }}")

        central = QWidget()
        central.setObjectName("Central")
        central.setStyleSheet(f"QWidget#Central {{ background: {C.BG}; }}")
        self.setCentralWidget(central)

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_metrics_strip())

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        body.addWidget(self._build_rail(), 0)
        self._center = self._build_center()
        body.addWidget(self._center, 1)
        body.addWidget(self._build_right_panel(), 0)
        root.addLayout(body, 1)
        root.addWidget(self._build_footer())

        # camera preview overlay + content panel + backdrop (children of central)
        self._cam_preview = CameraPreview(central)
        self._content_panel = ContentPanel(central)
        self._backdrop = DimBackdrop(central)
        self._backdrop.hide()

        # signals
        self._log_sig.connect(self._append_log)
        self._state_sig.connect(self._apply_state)
        self._content_sig.connect(self._show_content)
        self._reconfig_sig.connect(self._show_setup)
        self._camera_sig.connect(self._show_camera_frame)
        self._cam_stream_sig.connect(self._on_cam_stream)
        self._cam_frame_sig.connect(self._on_cam_frame)
        self._clipboard_sig.connect(self._show_clipboard_panel)
        self._cam_stop = threading.Event()

        # clipboard panel
        self._clipboard_panel = ClipboardPanel(central)
        self._clipboard_panel.action_requested.connect(self._on_clipboard_action)
        try:
            QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)
        except Exception:
            pass

        # clock + metrics timers
        self._clock_tmr = QTimer(self)
        self._clock_tmr.timeout.connect(self._tick_clock)
        self._clock_tmr.start(1000)
        self._tick_clock()
        self._metric_tmr = QTimer(self)
        self._metric_tmr.timeout.connect(self._update_metrics)
        self._metric_tmr.start(2000)
        self._update_metrics()

        # shortcuts
        QShortcut(QKeySequence("F4"), self).activated.connect(self._toggle_mute)
        QShortcut(QKeySequence("F11"), self).activated.connect(self._toggle_fullscreen)
        QShortcut(QKeySequence("Escape"), self).activated.connect(self._do_interrupt)

        self._ready = self._check_config()
        if not self._ready:
            QTimer.singleShot(50, self._show_setup)

    # ── header ──────────────────────────────────────────────────────────────
    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(64)
        w.setStyleSheet(f"background: {C.DARK}; border-bottom: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(20, 0, 20, 0)
        lay.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(1)
        self._title_lbl = QLabel(self._assistant_name.upper())
        self._title_lbl.setFont(sans_font(16, bold=True))
        self._title_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        title_col.addWidget(self._title_lbl)
        sub = "Just A Rather Very Intelligent System" if self._assistant_name.upper() in (
            "JARVIS", "J.A.R.V.I.S") else "Personal AI Assistant"
        self._sub_lbl = QLabel(sub)
        self._sub_lbl.setFont(sans_font(9))
        self._sub_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        title_col.addWidget(self._sub_lbl)
        lay.addLayout(title_col)

        badge = QLabel("MARK LI")
        badge.setFont(sans_font(8, bold=True))
        badge.setStyleSheet(f"""
            color: {C.PRI}; background: {C.PRI_GHO};
            border: 1px solid {C.PRI_DIM}; border-radius: 9px;
            padding: 3px 10px;
        """)
        lay.addWidget(badge)
        lay.addStretch()

        self._metrics_btn = QPushButton("Metrics")
        self._metrics_btn.setFixedHeight(30)
        self._metrics_btn.setCheckable(True)
        self._metrics_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._metrics_btn.setFont(sans_font(9, bold=True))
        self._metrics_btn.setToolTip("Toggle system metrics")
        self._metrics_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                           border: 1px solid {C.BORDER}; border-radius: 15px;
                           padding: 0 14px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}
            QPushButton:checked {{ color: {C.PRI}; border-color: {C.PRI_DIM};
                                   background: {C.PRI_GHO}; }}
        """)
        self._metrics_btn.toggled.connect(self._toggle_metrics)
        lay.addWidget(self._metrics_btn)

        clock_col = QVBoxLayout()
        clock_col.setSpacing(1)
        self._clock_lbl = QLabel("00:00:00")
        self._clock_lbl.setFont(mono_font(14, bold=True))
        self._clock_lbl.setStyleSheet(f"color: {C.WHITE}; background: transparent;")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_col.addWidget(self._clock_lbl)
        self._date_lbl = QLabel("")
        self._date_lbl.setFont(sans_font(9))
        self._date_lbl.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        self._date_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_col.addWidget(self._date_lbl)
        lay.addLayout(clock_col)
        return w

    def _tick_clock(self):
        self._clock_lbl.setText(time.strftime("%H:%M:%S"))
        self._date_lbl.setText(time.strftime("%a %d %b %Y"))

    # ── metrics strip ───────────────────────────────────────────────────────
    def _build_metrics_strip(self) -> QWidget:
        self._metrics_strip = QWidget()
        self._metrics_strip.setObjectName("MetricsStrip")
        self._metrics_strip.setStyleSheet(f"""
            QWidget#MetricsStrip {{ background: {C.BG};
                border-bottom: 1px solid {C.BORDER}; }}
        """)
        wrap = QVBoxLayout(self._metrics_strip)
        wrap.setContentsMargins(20, 10, 20, 12)
        wrap.setSpacing(8)

        card = QWidget()
        card.setObjectName("MetricsCard")
        card.setStyleSheet(f"""
            QWidget#MetricsCard {{ background: {C.PANEL};
                border: 1px solid {C.BORDER}; border-radius: 16px; }}
        """)
        grid = QGridLayout(card)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(8)

        self._bar_cpu = MetricBar("CPU", C.PRI)
        self._bar_mem = MetricBar("MEM", C.PRI)
        self._bar_net = MetricBar("NET", C.PRI)
        self._bar_gpu = MetricBar("GPU", C.PRI)
        self._bar_tmp = MetricBar("TMP", C.PRI)
        bars = [self._bar_cpu, self._bar_mem, self._bar_net, self._bar_gpu, self._bar_tmp]
        for i, b in enumerate(bars):
            grid.addWidget(b, i // 3, i % 3)

        info = QWidget()
        info.setStyleSheet("background: transparent;")
        ilay = QHBoxLayout(info)
        ilay.setContentsMargins(0, 0, 0, 0)
        ilay.setSpacing(20)
        self._uptime_lbl = QLabel("UP  --:--")
        self._uptime_lbl.setFont(mono_font(9, bold=True))
        self._uptime_lbl.setStyleSheet(f"color: {C.GREEN}; background: transparent;")
        ilay.addWidget(self._uptime_lbl)
        self._proc_lbl = QLabel("PROC  --")
        self._proc_lbl.setFont(mono_font(9))
        self._proc_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        ilay.addWidget(self._proc_lbl)
        os_name = {"Windows": "WIN", "Darwin": "macOS", "Linux": "LINUX"}.get(_OS, _OS.upper())
        os_lbl = QLabel(f"OS  {os_name}")
        os_lbl.setFont(mono_font(9))
        os_lbl.setStyleSheet(f"color: {C.TEXT_MED}; background: transparent;")
        ilay.addWidget(os_lbl)
        ilay.addStretch()
        grid.addWidget(info, 0, 3, 2, 1)

        wrap.addWidget(card)
        self._metrics_strip.setVisible(False)
        return self._metrics_strip

    def _toggle_metrics(self, on: bool):
        self._metrics_strip.setVisible(on)

    def _update_metrics(self):
        snap = _metrics.snapshot()
        cpu = snap["cpu"]
        self._bar_cpu.set_value(cpu, f"{cpu:.0f}%")
        mem = snap["mem"]
        self._bar_mem.set_value(mem, f"{mem:.0f}%")
        net = snap["net"]
        net_str = f"{net*1024:.0f}KB/s" if net < 1.0 else f"{net:.1f}MB/s"
        self._bar_net.set_value(min(100, net * 10), net_str)
        gpu = snap["gpu"]
        self._bar_gpu.set_value(gpu if gpu >= 0 else 0, f"{gpu:.0f}%" if gpu >= 0 else "N/A")
        tmp = snap["tmp"]
        self._bar_tmp.set_value(min(100, tmp) if tmp >= 0 else 0,
                                f"{tmp:.0f}\u00b0C" if tmp >= 0 else "N/A")
        try:
            el = time.time() - psutil.boot_time()
            self._uptime_lbl.setText(f"UP  {int(el//3600):02d}:{int((el%3600)//60):02d}")
        except Exception:
            self._uptime_lbl.setText("UP  --:--")
        try:
            self._proc_lbl.setText(f"PROC  {len(psutil.pids())}")
        except Exception:
            self._proc_lbl.setText("PROC  --")

    # ── left icon rail ──────────────────────────────────────────────────────
    def _rail_button(self, glyph: str, tip: str) -> QPushButton:
        b = QPushButton(glyph)
        b.setFixedSize(46, 46)
        b.setToolTip(tip)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_MED};
                           border: 1px solid transparent; border-radius: 14px;
                           font-size: 17px; }}
            QPushButton:hover {{ background: {C.PANEL};
                                 border-color: {C.BORDER}; color: {C.WHITE}; }}
            QPushButton:checked {{ background: {C.PRI_GHO};
                                   border-color: {C.PRI_DIM}; color: {C.PRI}; }}
        """)
        return b

    def _build_rail(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RAIL_W)
        w.setStyleSheet(f"background: {C.DARK}; border-right: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(9, 14, 9, 14)
        lay.setSpacing(10)
        lay.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        home = self._rail_button("\U0001F3E0", "Home")
        home.clicked.connect(lambda: self._hud_stack.setCurrentIndex(0))
        lay.addWidget(home, 0, Qt.AlignmentFlag.AlignHCenter)

        plugins = self._rail_button("\U0001F9E9", "Plugins")
        plugins.clicked.connect(self._open_plugin_manager)
        lay.addWidget(plugins, 0, Qt.AlignmentFlag.AlignHCenter)

        controls = self._rail_button("\u2699", "Controls & settings")
        controls.clicked.connect(self._open_controls)
        lay.addWidget(controls, 0, Qt.AlignmentFlag.AlignHCenter)

        lay.addStretch()

        self._mute_btn = self._rail_button("\U0001F3A7", "Mute microphone [F4]")
        self._mute_btn.clicked.connect(self._toggle_mute)
        lay.addWidget(self._mute_btn, 0, Qt.AlignmentFlag.AlignHCenter)

        self._interrupt_btn = self._rail_button("\u270B", "Interrupt [Esc]")
        self._interrupt_btn.clicked.connect(self._do_interrupt)
        lay.addWidget(self._interrupt_btn, 0, Qt.AlignmentFlag.AlignHCenter)
        self._style_mute_btn()
        return w

    # ── centre column ───────────────────────────────────────────────────────
    def _build_center(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C.BG};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 20, 24, 16)
        lay.setSpacing(14)

        self._orb = OrbWidget(self._face_path, self._assistant_name.upper())
        self._wave = WaveformBar()
        self._pill = StatePill()

        orb_page = QWidget()
        orb_page.setStyleSheet("background: transparent;")
        opl = QVBoxLayout(orb_page)
        opl.setContentsMargins(0, 0, 0, 0)
        opl.setSpacing(0)
        opl.addWidget(self._orb, 1)

        cam_page = QWidget()
        cam_page.setObjectName("CamPage")
        cam_page.setStyleSheet(f"""
            QWidget#CamPage {{ background: {C.DARK};
                border: 1px solid {C.BORDER_B}; border-radius: 18px; }}
        """)
        cpl = QVBoxLayout(cam_page)
        cpl.setContentsMargins(12, 10, 12, 12)
        cpl.setSpacing(8)
        crow = QHBoxLayout()
        clbl = QLabel("Live camera")
        clbl.setFont(sans_font(11, bold=True))
        clbl.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        crow.addWidget(clbl)
        crow.addStretch()
        cx = QPushButton("\u2715  Close")
        cx.setFont(sans_font(9))
        cx.setCursor(Qt.CursorShape.PointingHandCursor)
        cx.setStyleSheet(f"""
            QPushButton {{ color: {C.TEXT_MED}; background: transparent;
                           border: 1px solid {C.BORDER}; border-radius: 12px;
                           padding: 3px 12px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}
        """)
        cx.clicked.connect(self.stop_camera_stream)
        crow.addWidget(cx)
        cpl.addLayout(crow)
        self._cam_live_lbl = QLabel()
        self._cam_live_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._cam_live_lbl.setStyleSheet("background: transparent;")
        self._cam_live_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        cpl.addWidget(self._cam_live_lbl, 1)

        self._hud_stack = QStackedWidget()
        self._hud_stack.addWidget(orb_page)
        self._hud_stack.addWidget(cam_page)
        lay.addWidget(self._hud_stack, 1)
        lay.addWidget(self._pill, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self._wave)
        return w

    # ── right column ────────────────────────────────────────────────────────
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setFixedWidth(_RIGHT_W)
        w.setStyleSheet(f"background: {C.DARK}; border-left: 1px solid {C.BORDER};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        hdr = QLabel("Conversation")
        hdr.setFont(sans_font(11, bold=True))
        hdr.setStyleSheet(f"color: {C.TEXT}; background: transparent;")
        lay.addWidget(hdr)

        self._chat = ChatPanel()
        self._chat._ai_name_lc = self._assistant_name.lower()
        lay.addWidget(self._chat, 1)

        self._file_chip = FileChip()
        self._file_chip.removed.connect(self._clear_file)
        lay.addWidget(self._file_chip)

        self._composer = Composer()
        self._composer.send_requested.connect(self._send_text)
        self._composer.attach_clicked.connect(self._browse_file)
        lay.addWidget(self._composer)
        return w

    # ── footer ──────────────────────────────────────────────────────────────
    def _build_footer(self) -> QWidget:
        w = QWidget()
        w.setFixedHeight(30)
        w.setStyleSheet(f"background: {C.DARK}; border-top: 1px solid {C.BORDER};")
        lay = QHBoxLayout(w)
        lay.setContentsMargins(20, 0, 20, 0)
        hint = QLabel("[F4] Mute  ·  [F11] Fullscreen  ·  [Esc] Interrupt")
        hint.setFont(sans_font(9))
        hint.setStyleSheet(f"color: {C.TEXT_DIM}; background: transparent;")
        lay.addWidget(hint)
        lay.addStretch()
        by = QLabel("By FatihMakes")
        by.setFont(sans_font(9))
        by.setStyleSheet(f"color: {C.PRI_DIM}; background: transparent;")
        lay.addWidget(by)
        return w

    # ── state / log slots ───────────────────────────────────────────────────
    def _append_log(self, text: str):
        self._chat.append_log(text)

    def _apply_state(self, state: str):
        self._orb.state = state
        self._orb.speaking = (state == "SPEAKING")
        self._wave.state = state
        self._pill.state = state

    # ── content panel ───────────────────────────────────────────────────────
    def _show_content(self, title: str, text: str):
        try:
            self._content_panel.setGeometry(self.content_card_rect().toRect())
        except Exception:
            pass
        self._content_panel.present(title, text)

    # ── camera ──────────────────────────────────────────────────────────────
    def _show_camera_frame(self, img_bytes: bytes):
        self._cam_preview.show_frame(img_bytes)
        cw = self.centralWidget()
        self._cam_preview.setGeometry(
            cw.width() - _RIGHT_W - CameraPreview._W - 20,
            cw.height() - self._cam_preview.height() - 44,
            CameraPreview._W, self._cam_preview.height())

    def _on_cam_stream(self, start: bool) -> None:
        if start:
            self._hud_stack.setCurrentIndex(1)
        else:
            self._hud_stack.setCurrentIndex(0)
            self._cam_live_lbl.clear()

    def _on_cam_frame(self, data: bytes) -> None:
        px = QPixmap()
        px.loadFromData(data)
        if not px.isNull():
            w, h = self._cam_live_lbl.width(), self._cam_live_lbl.height()
            if w > 1 and h > 1:
                self._cam_live_lbl.setPixmap(px.scaled(
                    w, h, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))

    def start_camera_stream(self) -> None:
        self._cam_stop.clear()
        self._cam_stream_sig.emit(True)
        threading.Thread(target=self._cam_loop, daemon=True, name="cam-stream").start()

    def _cam_loop(self) -> None:
        try:
            import cv2
            cam_idx = 0
            try:
                cam_idx = int(_read_full_config().get("camera_index", 0))
            except Exception:
                cam_idx = 0
            try:
                backend = cv2.CAP_DSHOW if _OS == "Windows" else cv2.CAP_ANY
            except AttributeError:
                backend = 0
            cap = cv2.VideoCapture(cam_idx, backend)
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                return
            for _ in range(5):
                cap.read()
            while not self._cam_stop.wait(0.033) and cap.isOpened():
                ret, frame = cap.read()
                if ret and frame is not None:
                    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    self._cam_frame_sig.emit(buf.tobytes())
            cap.release()
        except Exception as e:
            print(f"[Camera] Stream error: {e}")
        finally:
            self._cam_stream_sig.emit(False)

    def stop_camera_stream(self) -> None:
        self._cam_stop.set()

    # ── clipboard ───────────────────────────────────────────────────────────
    def _on_clipboard_changed(self):
        try:
            text = QApplication.clipboard().text().strip()
            if len(text) >= 10:
                self._clipboard_sig.emit(text)
        except Exception:
            pass

    def _show_clipboard_panel(self, text: str):
        self._clipboard_panel.show_clipboard(text)
        self._position_clipboard_panel()

    def _position_clipboard_panel(self):
        cw = self.centralWidget()
        ph = self._clipboard_panel.sizeHint().height() or ClipboardPanel._H
        x = (cw.width() - ClipboardPanel._W) // 2
        y = cw.height() - ph - 12
        self._clipboard_panel.setGeometry(x, y, ClipboardPanel._W, ph)
        self._clipboard_panel.raise_()

    def _on_clipboard_action(self, cmd: str):
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(cmd,), daemon=True).start()

    # ── interacting ─────────────────────────────────────────────────────────
    def _do_interrupt(self):
        if self.on_interrupt:
            self.on_interrupt()

    def _toggle_mute(self):
        self._muted = not self._muted
        self._orb.muted = self._muted
        self._style_mute_btn()
        if self._muted:
            self._apply_state("MUTED")
            self._chat.append_log("SYS: Microphone muted.")
        else:
            self._apply_state("LISTENING")
            self._chat.append_log("SYS: Microphone active.")

    def _style_mute_btn(self):
        if self._muted:
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{ background: rgba(255,77,106,0.14); color: {C.MUTED_C};
                               border: 1px solid {C.MUTED_C}; border-radius: 14px;
                               font-size: 17px; }}
            """)
        else:
            self._mute_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {C.TEXT_MED};
                               border: 1px solid transparent; border-radius: 14px;
                               font-size: 17px; }}
                QPushButton:hover {{ background: {C.PANEL}; color: {C.WHITE};
                                     border-color: {C.BORDER}; }}
            """)

    def _send_text(self, txt: str):
        self._chat.append_log(f"You: {txt}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(txt,), daemon=True).start()

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a file", str(Path.home()), "All Files (*.*)")
        if path:
            self._on_file_selected(path)

    def _on_file_selected(self, path: str):
        p = Path(path)
        if not p.is_file():
            return
        self._current_file = path
        self._file_chip.set_file(path)
        try:
            size = _fmt_size(p.stat().st_size)
        except Exception:
            size = "?"
        self._chat.append_log(f"FILE: {p.name} ({size}) loaded")
        if self.on_text_command:
            msg = (f"[FILE_UPLOADED] path={path} | name={p.name} | "
                   f"type={p.suffix.lstrip('.')} | size={size} | "
                   f"Briefly tell the user you can see the file '{p.name}' "
                   f"({size}) has been uploaded and ask what they'd like to do with it.")
            threading.Thread(target=self.on_text_command, args=(msg,), daemon=True).start()

    def _clear_file(self):
        self._current_file = None
        self._file_chip.hide()

    # ── drag & drop anywhere on the window ──────────────────────────────────
    def dragEnterEvent(self, e: QDragEnterEvent):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e: QDropEvent):
        urls = e.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if Path(path).is_file():
                self._on_file_selected(path)
        e.acceptProposedAction()

    # ── overlays ────────────────────────────────────────────────────────────
    def _clamp_overlay(self, ov: QWidget) -> None:
        """Centre an overlay over the central widget and clamp it so it can
        never extend outside the window."""
        cw = self.centralWidget()
        if cw is None:
            return
        W, H = cw.width(), cw.height()
        ow = ov.width() or 420
        oh = ov.height() or 400
        ow = max(120, min(ow, W))
        oh = max(100, min(oh, H))
        x = max(0, (W - ow) // 2)
        y = max(0, (H - oh) // 2)
        x = min(x, max(0, W - ow))
        y = min(y, max(0, H - oh))
        ov.setGeometry(x, y, ow, oh)

    def _centre_rect(self) -> QRectF:
        cw = self.centralWidget()
        if cw is None:
            return QRectF(0, 0, 0, 0)
        c = getattr(self, "_center", None)
        if c is not None and c.width() > 0 and c.height() > 0:
            return QRectF(c.geometry())
        return QRectF(0, 0, cw.width(), cw.height())

    def content_card_rect(self) -> QRectF:
        """Target rect for the slide-up content panel: anchored inside the
        centre orb area, ~16px margins, ~260px tall, fully inside central."""
        cw = self.centralWidget()
        W = cw.width() if cw is not None else _DEFAULT_W
        H = cw.height() if cw is not None else _DEFAULT_H
        margin = 16
        card_h = min(260, max(120, H - 2 * margin))
        cr = self._centre_rect()
        if cr.width() > 0 and cr.height() > 0:
            x = int(cr.x()) + margin
            w = int(cr.width()) - 2 * margin
            bottom = int(cr.y() + cr.height()) - margin   # above waveform/bottom
        else:
            x = margin
            w = W - 2 * margin
            bottom = H - margin
        w = max(80, w)
        y = bottom - card_h
        # clamp fully inside the central widget
        w = min(w, W - 2 * margin) if W - 2 * margin > 80 else max(80, W)
        x = max(0, min(x, max(0, W - w)))
        if y < 0:
            y = 0
        if y + card_h > H:
            y = max(0, H - card_h)
        if x + w > W:
            w = max(1, W - x)
        return QRectF(x, y, w, card_h)

    def _show_overlay(self, ov: QWidget) -> None:
        cw = self.centralWidget()
        self._backdrop.setGeometry(0, 0, cw.width(), cw.height())
        self._backdrop.show()
        self._backdrop.raise_()
        self._clamp_overlay(ov)
        ov.show()
        ov.raise_()

    def _hide_backdrop_if_idle(self):
        for ov in (self._overlay, self._remote_overlay, self._customize_overlay,
                   self._plugin_manager_overlay):
            if ov is not None and ov.isVisible():
                return
        self._backdrop.hide()

    def _check_config(self) -> bool:
        if not API_FILE.exists():
            return False
        try:
            d = json.loads(API_FILE.read_text(encoding="utf-8"))
            return bool(d.get("gemini_api_key")) and bool(d.get("os_system"))
        except Exception:
            return False

    def _show_setup(self):
        if self._overlay and self._overlay.isVisible():
            return
        cw = self.centralWidget()
        ov = SetupOverlay(cw)
        ov.setFixedSize(460, 400)
        ov.done.connect(self._on_setup_done)
        self._overlay = ov
        self._show_overlay(ov)

    def _on_setup_done(self, key: str, os_name: str):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        data = _read_full_config()
        data["gemini_api_key"] = key
        data["os_system"] = os_name
        _write_config(data)
        self._ready = True
        if self._overlay:
            self._overlay.hide()
            self._overlay = None
        self._hide_backdrop_if_idle()
        self._apply_state("LISTENING")
        self._assistant_name = (_read_full_config().get("assistant_name") or "JARVIS").strip()
        self._chat.append_log(
            f"SYS: Initialised. OS={os_name.upper()}. {self._assistant_name} online.")

    def _open_controls(self):
        if self._plugin_manager_overlay is not None:
            pass
        cw = self.centralWidget()
        ov = self._build_controls_panel(cw)
        self._controls_overlay = ov
        self._show_overlay(ov)

    def _build_controls_panel(self, parent) -> QWidget:
        ov = OverlayCard(parent)
        ov.setStyleSheet(ov._card_qss())
        ov.setFixedWidth(400)
        lay = QVBoxLayout(ov)
        lay.setContentsMargins(24, 20, 24, 20)
        lay.setSpacing(9)

        hdr = QLabel("Controls")
        hdr.setFont(sans_font(15, bold=True))
        hdr.setStyleSheet(f"color: {C.PRI}; background: transparent;")
        lay.addWidget(hdr)

        def _btn(txt, slot, primary=False, tip=""):
            b = QPushButton(txt)
            b.setFixedHeight(38)
            b.setFont(sans_font(10, bold=primary))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if tip:
                b.setToolTip(tip)
            if primary:
                b.setStyleSheet(f"""
                    QPushButton {{ background: {C.PRI}; color: #04060a; border: none;
                                   border-radius: 13px; }}
                    QPushButton:hover {{ background: {C.WHITE}; }}
                """)
            else:
                b.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {C.TEXT};
                                   border: 1px solid {C.BORDER}; border-radius: 13px; }}
                    QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B};
                                         background: {C.PANEL}; }}
                """)
            b.clicked.connect(slot)
            lay.addWidget(b)
            return b

        _btn("Remote control", self._open_remote, primary=True)
        _btn("Fullscreen  [F11]", self._toggle_fullscreen)
        _btn("Create desktop shortcut", self._create_desktop_shortcut)
        self._autostart_btn = _btn("Auto-start", self._toggle_autostart)
        self._update_autostart_btn(self._check_autostart())
        _btn("Customise assistant", self._open_customize)
        self._brief_btn = _btn("Morning brief", self._toggle_brief)
        self._update_brief_btn(self._safe_brief_enabled())
        _btn("Plugins", self._open_plugin_manager)

        close = QPushButton("CLOSE")
        close.setFixedHeight(34)
        close.setFont(sans_font(9))
        close.setCursor(Qt.CursorShape.PointingHandCursor)
        close.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {C.TEXT_DIM};
                           border: 1px solid {C.BORDER}; border-radius: 13px; }}
            QPushButton:hover {{ color: {C.WHITE}; border-color: {C.BORDER_B}; }}
        """)
        close.clicked.connect(lambda: (ov.hide(), self._hide_backdrop_if_idle()))
        lay.addWidget(close)
        ov.adjustSize()
        return ov

    # ── remote ──────────────────────────────────────────────────────────────
    def notify_phone_connected(self) -> None:
        if self._remote_overlay and self._remote_overlay.isVisible():
            self._remote_overlay.mark_connected()

    def _open_remote(self):
        if not self.on_remote_clicked:
            self._chat.append_log("SYS: Dashboard not running — remote unavailable.")
            return
        result = self.on_remote_clicked()
        if not result:
            self._chat.append_log("SYS: Could not generate remote key.")
            return
        url = result[0]
        key = result[1]
        auto = result[2] if len(result) >= 3 else ""
        manual = result[3] if len(result) >= 4 else url
        if self._remote_overlay:
            self._remote_overlay._do_close()
        cw = self.centralWidget()
        ov = RemoteKeyOverlay(url, key, auto_login_url=auto, manual_url=manual,
                              expiry_secs=600, parent=cw)
        ov.setFixedSize(RemoteKeyOverlay._OW, RemoteKeyOverlay._OH)
        ov.set_new_key_callback(self.on_remote_clicked)
        ov.closed.connect(lambda: (setattr(self, '_remote_overlay', None),
                                   self._hide_backdrop_if_idle()))
        self._remote_overlay = ov
        self._show_overlay(ov)
        self._chat.append_log(f"SYS: Remote key generated — manual: {manual or url}")

    # ── customise ───────────────────────────────────────────────────────────
    def _open_customize(self):
        cfg = _read_full_config()
        if self._customize_overlay:
            self._customize_overlay.hide()
        cw = self.centralWidget()
        ov = CustomizeOverlay(
            cfg.get("assistant_name", "JARVIS") or "JARVIS",
            cfg.get("user_name", ""),
            cfg.get("ui_color", "") or DEFAULT_UI_COLOR,
            parent=cw)
        ov.setFixedSize(CustomizeOverlay._OW, min(CustomizeOverlay._OH, cw.height() - 24))
        ov.on_preview = self._preview_ui_color
        ov.saved.connect(self._apply_name_update)
        self._customize_overlay = ov
        self._show_overlay(ov)

    def _preview_ui_color(self, hex_color: str):
        old = current_palette()
        if apply_ui_accent(hex_color):
            retheme_all_widgets(old, current_palette())

    def _apply_name_update(self, name: str, user_name: str, ui_color: str = ""):
        self._assistant_name = name.strip() or "JARVIS"
        display = self._assistant_name.upper()
        self.setWindowTitle(f"{display} — MARK LI")
        self._title_lbl.setText(display)
        self._sub_lbl.setText(
            "Just A Rather Very Intelligent System"
            if display in ("JARVIS", "J.A.R.V.I.S") else "Personal AI Assistant")
        self._chat._ai_name_lc = self._assistant_name.lower()
        self._orb._assistant_name = display

        color_changed = False
        if ui_color:
            old = current_palette()
            if apply_ui_accent(ui_color):
                retheme_all_widgets(old, current_palette())
                color_changed = old["PRI"] != C.PRI
        try:
            data = _read_full_config()
            data["assistant_name"] = self._assistant_name
            data["user_name"] = user_name.strip()
            if ui_color:
                data["ui_color"] = ui_color.strip().lower()
            _write_config(data)
            self._chat.append_log(f"SYS: Identity updated — {display}")
            if color_changed:
                self._chat.append_log(f"SYS: UI colour applied — {ui_color}")
        except Exception as e:
            self._chat.append_log(f"ERR: Config save failed — {e}")
        if self._customize_overlay:
            self._customize_overlay.hide()
        self._hide_backdrop_if_idle()

    # ── plugins ─────────────────────────────────────────────────────────────
    def _open_plugin_manager(self):
        plugins = self.get_plugins() if self.get_plugins else []
        cw = self.centralWidget()
        ov = PluginManagerOverlay(plugins, parent=cw)
        ov.adjustSize()
        self._plugin_manager_overlay = ov
        self._show_overlay(ov)

    # ── autostart / brief helpers ───────────────────────────────────────────
    def _safe_brief_enabled(self) -> bool:
        try:
            from memory.config_manager import get_brief_enabled
            return bool(get_brief_enabled())
        except Exception:
            return False

    def _toggle_brief(self):
        try:
            from memory.config_manager import get_brief_enabled, save_brief_enabled
            new_val = not get_brief_enabled()
            save_brief_enabled(new_val)
        except Exception:
            new_val = False
        self._update_brief_btn(new_val)

    def _update_brief_btn(self, enabled: bool):
        if not hasattr(self, '_brief_btn'):
            return
        self._brief_btn.setText("Morning brief: " + ("ON" if enabled else "OFF"))

    # ── fullscreen ──────────────────────────────────────────────────────────
    def _toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ── reposition children on resize ───────────────────────────────────────
    def resizeEvent(self, event):
        super().resizeEvent(event)
        cw = self.centralWidget()
        if cw is None:
            return
        if self._backdrop.isVisible():
            self._backdrop.setGeometry(0, 0, cw.width(), cw.height())
        for ov in (self._overlay, self._remote_overlay, self._customize_overlay,
                   getattr(self, '_controls_overlay', None),
                   self._plugin_manager_overlay):
            if ov is not None and ov.isVisible():
                self._clamp_overlay(ov)
        if self._content_panel.isVisible():
            self._content_panel.setGeometry(self.content_card_rect().toRect())
        if self._cam_preview.isVisible():
            self._cam_preview.setGeometry(
                cw.width() - _RIGHT_W - CameraPreview._W - 20,
                cw.height() - self._cam_preview.height() - 44,
                CameraPreview._W, self._cam_preview.height())
        if self._clipboard_panel.isVisible():
            self._position_clipboard_panel()

    # ── desktop shortcut (ported faithfully) ────────────────────────────────
    @staticmethod
    def _build_jarvis_icon(out_path: Path) -> bool:
        try:
            import PIL.Image
            import PIL.ImageDraw
            import PIL.ImageFilter
        except ImportError:
            return False

        CYAN = (0, 212, 255)
        DIM = (0, 100, 140)
        DARK = (10, 11, 13)
        GLOW = (0, 160, 200)
        WHITE = (220, 240, 255)

        def _render(sz: int):
            S = sz * 4
            img = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            d = PIL.ImageDraw.Draw(img)
            cx = cy = S // 2
            R = S // 2 - 2
            d.ellipse([cx - R, cy - R, cx + R, cy + R], fill=(*DARK, 255))
            lw = max(2, S // 40)
            d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=(*CYAN, 220), width=lw)
            R2 = int(R * 0.72)
            d.ellipse([cx - R2, cy - R2, cx + R2, cy + R2], outline=(*DIM, 180),
                      width=max(1, lw // 2))
            R_inner, R_outer = int(R * 0.30), int(R * 0.62)
            for i in range(6):
                a = math.radians(i * 60 - 30)
                d.line([cx + int(R_inner * math.cos(a)), cy + int(R_inner * math.sin(a)),
                        cx + int(R_outer * math.cos(a)), cy + int(R_outer * math.sin(a))],
                       fill=(*GLOW, 200), width=max(1, S // 80))
            Ri = int(R * 0.26)
            d.ellipse([cx - Ri, cy - Ri, cx + Ri, cy + Ri], outline=(*CYAN, 255),
                      width=max(2, lw))
            glow = PIL.Image.new("RGBA", (S, S), (0, 0, 0, 0))
            gd = PIL.ImageDraw.Draw(glow)
            Rc = int(R * 0.13)
            gd.ellipse([cx - Rc * 2, cy - Rc * 2, cx + Rc * 2, cy + Rc * 2], fill=(*CYAN, 110))
            glow = glow.filter(PIL.ImageFilter.GaussianBlur(S // 14))
            img = PIL.Image.alpha_composite(img, glow)
            d = PIL.ImageDraw.Draw(img)
            d.ellipse([cx - Rc, cy - Rc, cx + Rc, cy + Rc], fill=(*WHITE, 255))
            return img.resize((sz, sz), PIL.Image.LANCZOS)

        try:
            sizes = [256, 128, 64, 48, 32, 16]
            frames = [_render(s) for s in sizes]
            frames[0].save(out_path, format="ICO", append_images=frames[1:],
                           sizes=[(s, s) for s in sizes])
            return True
        except Exception as e:
            print(f"[Shortcut] icon generation failed: {e}")
            return False

    @staticmethod
    def _create_lnk_windows(lnk: str, target: str, args: str,
                             work_dir: str, icon_loc: str) -> None:
        try:
            from win32com.client import Dispatch  # type: ignore
            sh = Dispatch("WScript.Shell")
            sc = sh.CreateShortCut(lnk)
            sc.TargetPath = target
            sc.Arguments = f'"{args}"'
            sc.WorkingDirectory = work_dir
            sc.Description = "MARK LI AI Assistant"
            sc.IconLocation = icon_loc
            sc.save()
            return
        except ImportError:
            pass
        vbs = "\n".join([
            'Set ws = CreateObject("WScript.Shell")',
            f'Set sc = ws.CreateShortcut("{lnk}")',
            f'sc.TargetPath = "{target}"',
            f'sc.Arguments = Chr(34) & "{args}" & Chr(34)',
            f'sc.WorkingDirectory = "{work_dir}"',
            'sc.Description = "MARK LI AI Assistant"',
            f'sc.IconLocation = "{icon_loc}"',
            'sc.Save',
        ])
        import tempfile
        fd, tmp = tempfile.mkstemp(suffix=".vbs")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(vbs)
            proc = subprocess.Popen(["wscript.exe", "/nologo", tmp], **_WIN_HIDE)
            proc.wait(timeout=10)
        finally:
            try:
                os.unlink(tmp)
            except Exception:
                pass

    @staticmethod
    def _get_desktop_dir() -> Path:
        home = Path.home()
        o = platform.system()
        if o == "Windows":
            try:
                import ctypes
                from ctypes import wintypes

                class _GUID(ctypes.Structure):
                    _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                                ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

                fid = _GUID(0xB4BFCC3A, 0xDB2C, 0x424C,
                            (ctypes.c_ubyte * 8)(0xB0, 0x29, 0x7F, 0xE9, 0x9A, 0x87, 0xC6, 0x41))
                buf = ctypes.c_wchar_p()
                if ctypes.windll.shell32.SHGetKnownFolderPath(
                        ctypes.byref(fid), 0, None, ctypes.byref(buf)) == 0:
                    p = Path(buf.value)
                    ctypes.windll.ole32.CoTaskMemFree(buf)
                    if p.is_dir():
                        return p
            except Exception:
                pass
            try:
                import winreg
                with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER,
                        r"Software\Microsoft\Windows\CurrentVersion"
                        r"\Explorer\User Shell Folders") as key:
                    val, _t = winreg.QueryValueEx(key, "Desktop")
                p = Path(os.path.expandvars(val))
                if p.is_dir():
                    return p
            except Exception:
                pass
        elif o == "Linux":
            try:
                out = subprocess.run(["xdg-user-dir", "DESKTOP"],
                                     capture_output=True, text=True, timeout=5)
                p = Path(out.stdout.strip())
                if out.stdout.strip() and p != home and p.is_dir():
                    return p
            except Exception:
                pass
            try:
                cfg = home / ".config" / "user-dirs.dirs"
                for line in cfg.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line.startswith("XDG_DESKTOP_DIR"):
                        val = line.split("=", 1)[1].strip().strip('"')
                        p = Path(val.replace("$HOME", str(home)))
                        if p != home and p.is_dir():
                            return p
            except Exception:
                pass
        return home / "Desktop"

    def _create_desktop_shortcut(self):
        import stat as _stat
        script = Path(__file__).resolve().parent / "main.py"
        python = Path(sys.executable)
        desktop = self._get_desktop_dir()
        ico_path = Path(__file__).resolve().parent / "config" / "markli.ico"
        if not ico_path.exists():
            try:
                ico_path.parent.mkdir(parents=True, exist_ok=True)
            except Exception:
                pass
            self._build_jarvis_icon(ico_path)
        try:
            o = platform.system()
            if o == "Windows":
                pythonw = python.parent / "pythonw.exe"
                target = str(pythonw if pythonw.exists() else python)
                lnk = str(desktop / "MARK LI.lnk")
                icon_loc = str(ico_path) if ico_path.exists() else f"{target},0"
                self._create_lnk_windows(lnk, target, str(script), str(script.parent), icon_loc)
            elif o == "Darwin":
                app = desktop / "MARK LI.app"
                mac_dir = app / "Contents" / "MacOS"
                res_dir = app / "Contents" / "Resources"
                mac_dir.mkdir(parents=True, exist_ok=True)
                res_dir.mkdir(exist_ok=True)
                launcher = mac_dir / "MARKLI"
                launcher.write_text(
                    "#!/usr/bin/env bash\n"
                    f'cd "{script.parent}"\n'
                    f'exec "{python}" "{script}"\n')
                launcher.chmod(launcher.stat().st_mode | _stat.S_IEXEC | _stat.S_IXGRP | _stat.S_IXOTH)
                (app / "Contents" / "Info.plist").write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                    '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                    '<plist version="1.0"><dict>\n'
                    '  <key>CFBundleExecutable</key><string>MARKLI</string>\n'
                    '  <key>CFBundleIdentifier</key><string>com.markli.assistant</string>\n'
                    '  <key>CFBundleName</key><string>MARK LI</string>\n'
                    '  <key>CFBundlePackageType</key><string>APPL</string>\n'
                    '  <key>CFBundleVersion</key><string>1.0</string>\n'
                    '</dict></plist>\n')
                try:
                    import PIL.Image
                    icns = res_dir / "AppIcon.icns"
                    PIL.Image.open(ico_path).save(icns, format="ICNS")
                    plist = app / "Contents" / "Info.plist"
                    txt = plist.read_text()
                    plist.write_text(txt.replace(
                        '</dict></plist>',
                        '  <key>CFBundleIconFile</key><string>AppIcon</string>\n</dict></plist>\n'))
                except Exception:
                    pass
            else:
                png_path = ico_path.with_suffix(".png")
                if not png_path.exists() and ico_path.exists():
                    try:
                        import PIL.Image
                        PIL.Image.open(ico_path).resize((256, 256), PIL.Image.LANCZOS).save(
                            png_path, format="PNG")
                    except Exception:
                        png_path = ico_path
                icon_line = f"Icon={png_path}\n" if png_path.exists() else ""
                desk = desktop / "MARK LI.desktop"
                desk.write_text(
                    "[Desktop Entry]\n"
                    "Name=MARK LI\n"
                    f"Exec={python} {script}\n"
                    f"Path={script.parent}\n"
                    "Type=Application\n"
                    "Terminal=false\n"
                    "Categories=Utility;\n" + icon_line)
                desk.chmod(desk.stat().st_mode | 0o755)
            self._chat.append_log("SYS: Desktop shortcut created.")
        except Exception as e:
            self._chat.append_log(f"ERR: Shortcut failed — {e}")

    # ── auto-start ──────────────────────────────────────────────────────────
    def _check_autostart(self) -> bool:
        try:
            if _OS == "Windows":
                import winreg
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_READ)
                try:
                    winreg.QueryValueEx(key, "JARVIS_AI")
                    return True
                except FileNotFoundError:
                    return False
                finally:
                    winreg.CloseKey(key)
            elif _OS == "Darwin":
                return (Path.home() / "Library" / "LaunchAgents"
                        / "com.jarvis.assistant.plist").exists()
            else:
                return (Path.home() / ".config" / "autostart" / "jarvis.desktop").exists()
        except Exception:
            return False

    def _toggle_autostart(self):
        currently_on = self._check_autostart()
        try:
            script = str(Path(__file__).resolve().parent / "main.py")
            if _OS == "Windows":
                import winreg
                reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                    winreg.KEY_ALL_ACCESS)
                if currently_on:
                    winreg.DeleteValue(reg, "JARVIS_AI")
                else:
                    pythonw = Path(sys.executable).parent / "pythonw.exe"
                    exe = str(pythonw if pythonw.exists() else sys.executable)
                    winreg.SetValueEx(reg, "JARVIS_AI", 0, winreg.REG_SZ, f'"{exe}" "{script}"')
                winreg.CloseKey(reg)
            elif _OS == "Darwin":
                plist_dir = Path.home() / "Library" / "LaunchAgents"
                plist_dir.mkdir(parents=True, exist_ok=True)
                plist = plist_dir / "com.jarvis.assistant.plist"
                if currently_on:
                    plist.unlink(missing_ok=True)
                else:
                    plist.write_text(
                        '<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                        '<plist version="1.0"><dict>\n'
                        '  <key>Label</key><string>com.jarvis.assistant</string>\n'
                        '  <key>ProgramArguments</key><array>\n'
                        f'    <string>{sys.executable}</string>\n'
                        f'    <string>{script}</string>\n'
                        '  </array>\n'
                        '  <key>RunAtLoad</key><true/>\n'
                        '</dict></plist>\n')
            else:
                desk_dir = Path.home() / ".config" / "autostart"
                desk_dir.mkdir(parents=True, exist_ok=True)
                desk = desk_dir / "jarvis.desktop"
                if currently_on:
                    desk.unlink(missing_ok=True)
                else:
                    desk.write_text(
                        "[Desktop Entry]\n"
                        f"Name={self._assistant_name}\n"
                        f"Exec={sys.executable} {script}\n"
                        "Type=Application\nTerminal=false\n"
                        "X-GNOME-Autostart-enabled=true\n")
            enabled = not currently_on
            self._update_autostart_btn(enabled)
            self._chat.append_log(f"SYS: Auto-start {'enabled' if enabled else 'disabled'}.")
        except Exception as e:
            self._chat.append_log(f"ERR: Auto-start failed — {e}")

    def _update_autostart_btn(self, enabled: bool):
        if not hasattr(self, '_autostart_btn'):
            return
        self._autostart_btn.setText("Auto-start: " + ("ON" if enabled else "OFF"))


# ────────────────────────────────────────────────────────────────────────────
#  Root shim + public JarvisUI façade (byte-compatible with main.py)
# ────────────────────────────────────────────────────────────────────────────
class _RootShim:
    def __init__(self, app: QApplication):
        self._app = app

    def mainloop(self):
        self._app.exec()

    def protocol(self, *_):
        pass


class JarvisUI:
    def __init__(self, face_path: str, size=None):
        self._app = QApplication.instance() or QApplication(sys.argv)
        self._app.setStyle("Fusion")
        self._win = MainWindow(face_path)
        self._win.show()
        self.root = _RootShim(self._app)

    @property
    def muted(self) -> bool:
        return self._win._muted

    @muted.setter
    def muted(self, v: bool):
        if v != self._win._muted:
            self._win._toggle_mute()

    @property
    def current_file(self) -> str | None:
        return self._win._drop_zone.current_file()

    @property
    def on_text_command(self):
        return self._win.on_text_command

    @on_text_command.setter
    def on_text_command(self, cb):
        self._win.on_text_command = cb

    @property
    def on_remote_clicked(self):
        return self._win.on_remote_clicked

    @on_remote_clicked.setter
    def on_remote_clicked(self, cb):
        self._win.on_remote_clicked = cb

    @property
    def on_interrupt(self):
        return self._win.on_interrupt

    @on_interrupt.setter
    def on_interrupt(self, cb):
        self._win.on_interrupt = cb

    @property
    def get_plugins(self):
        return self._win.get_plugins

    @get_plugins.setter
    def get_plugins(self, cb):
        self._win.get_plugins = cb

    def notify_phone_connected(self) -> None:
        self._win.notify_phone_connected()

    def set_state(self, state: str):
        self._win._state_sig.emit(state)

    def write_log(self, text: str):
        self._win._log_sig.emit(text)

    def wait_for_api_key(self):
        while not self._win._ready:
            time.sleep(0.1)

    def show_content(self, title: str, text: str):
        self._win._content_sig.emit(title[:48], text[:4000])

    def prompt_reconfig(self):
        self._win._ready = False
        self._win._reconfig_sig.emit()

    def show_camera_frame(self, img_bytes: bytes):
        self._win._camera_sig.emit(img_bytes)

    def start_camera_stream(self) -> None:
        self._win.start_camera_stream()

    def stop_camera_stream(self) -> None:
        self._win.stop_camera_stream()

    @property
    def assistant_name(self) -> str:
        return self._win._assistant_name

    def start_speaking(self):
        self.set_state("SPEAKING")

    def stop_speaking(self):
        if not self.muted:
            self.set_state("LISTENING")
