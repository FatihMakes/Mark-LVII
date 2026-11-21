"""gui/reactor.py — the reactor core, drawn in three dimensions.

The flat ring stack it replaces was a picture of a machine; this is a small
model of one. A holographic sphere sits above a projector platform, two
gyroscope rings turn through it on different axes, and an orbit ring carries
three tracers round the equator. Everything is projected from real 3-D points
through a camera tilted down at the scene, so the rings foreshorten into
ellipses, pass behind the sphere and come out in front of it.

Depth is what sells it, and depth is cheap: every line segment knows how far
it is from the camera. Segments behind the sphere are drawn before it and
dimmer; segments in front are drawn after it and brighter. That ordering and
that falloff are the whole trick — no z-buffer, no GPU, no new dependency.

What does not move is not redrawn. The platform's rings and the globe's lines
of latitude turn about the vertical axis, and a circle turned about its own
axis is the same circle — so they are drawn once into two cached layers and
blitted every frame after that. Only the gyroscope rings, the meridians and
the things that follow the voice are drawn per frame. Measured on the first
version, which redrew everything, this halves the cost of a frame.

Like the face in core/avatar.py it is software QPainter, it takes its colours
as arguments so the accent picker retints it, and everything that moves means
something: the spin rate is the assistant's state, the sphere's inner light
and the platform's spectrum ticks are the real audio level.
"""
from __future__ import annotations

import math

import numpy as np
from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter, QPen, QPixmap,
                         QRadialGradient)

_DISPLAY = ["Bahnschrift", "Segoe UI", "SF Pro Display", "Helvetica Neue",
            "Noto Sans", "DejaVu Sans"]

_PITCH = math.radians(17.0)     # the camera looks down at the platform
_CAM_D = 4.2                    # perspective distance, in core radii
_N_RING = 72                    # points on a ring
_N_GLOBE = 44                   # points on a globe line
_FLOOR_Y = -1.02                # the platform, below the sphere's centre
_SPHERE = 0.46                  # sphere radius, in core radii


def _rx(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _ry(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def _rz(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _with_alpha(col: QColor, a: float) -> QColor:
    c = QColor(col)
    c.setAlphaF(max(0.0, min(1.0, a)))
    return c


class Reactor3D:
    """State + renderer. `step()` advances it, `paint()` draws a frame."""

    # Vertical extent in core radii: the highest mote above the centre, and the
    # bottom of the name below it. Measured through the projection, not guessed —
    # the platform's front edge is nearer the camera, so perspective enlarges it.
    TOP = 1.05
    BOTTOM = 2.05

    def __init__(self):
        t = np.linspace(0.0, 2 * math.pi, _N_RING, endpoint=False)
        self._ring = np.vstack([np.cos(t), np.zeros_like(t), np.sin(t)])   # unit circle, XZ plane
        g = np.linspace(0.0, 2 * math.pi, _N_GLOBE, endpoint=False)
        self._glat = []
        for lat in (-58, -30, 0, 30, 58):
            la = math.radians(lat)
            self._glat.append(np.vstack([np.cos(g) * math.cos(la),
                                         np.full_like(g, math.sin(la)),
                                         np.sin(g) * math.cos(la)]))
        self._glon = []
        for k in range(6):
            lo = k * math.pi / 6
            self._glon.append(np.vstack([np.cos(g) * math.cos(lo),
                                         np.sin(g),
                                         np.cos(g) * math.sin(lo)]))
        rng = np.random.default_rng(57)
        self._motes = [(float(rng.uniform(1.18, 1.55)), float(rng.uniform(0, 2 * math.pi)),
                        float(rng.uniform(-0.55, 0.55)), float(rng.uniform(0.25, 0.9)))
                       for _ in range(22)]
        self.spin = 0.0
        self._view = _rx(_PITCH)
        self._cache_key = None
        self._under: QPixmap | None = None      # platform + back half of the latitudes
        self._lat_front: QPixmap | None = None  # front half of the latitudes
        self._box = QRectF()

    # ── motion ────────────────────────────────────────────────────────────────
    def step(self, dt: float, speaking: bool, thinking: bool, muted: bool) -> None:
        dt = min(0.10, max(0.0, dt))
        rate = 0.12 if muted else 0.38 + (1.5 if thinking else 0.0) + (0.8 if speaking else 0.0)
        self.spin += dt * rate

    # ── projection ────────────────────────────────────────────────────────────
    def _project(self, pts, cx, cy, r):
        v = self._view @ pts
        s = _CAM_D / (_CAM_D - v[2])
        return cx + v[0] * s * r, cy - v[1] * s * r, v[2], s

    @staticmethod
    def _cued(p, X, Y, Z, col, a_front, a_back, width, part):
        """Draw one side of a closed polyline — the half behind the depth plane
        or the half in front of it — in three brightness buckets."""
        zm = (Z + np.roll(Z, -1)) * 0.5
        if part == "back":
            mask = zm < 0
            if not mask.any():
                return
            alpha = a_back * (0.35 + 0.65 * np.maximum(1.0 + zm, 0.0))
        else:
            mask = zm >= 0
            if not mask.any():
                return
            alpha = a_front * (0.55 + 0.45 * np.minimum(zm, 1.0))
        idx = np.flatnonzero(mask)
        av = alpha[idx]
        top = float(av.max())
        levels = np.minimum((av * (2.999 / max(1e-6, top))).astype(np.int8), 2).tolist()
        xs, ys = X[idx].tolist(), Y[idx].tolist()
        xe, ye = np.roll(X, -1)[idx].tolist(), np.roll(Y, -1)[idx].tolist()
        buckets = ([], [], [])
        for i, lv in enumerate(levels):
            buckets[lv].append(QLineF(xs[i], ys[i], xe[i], ye[i]))
        for k, lines in enumerate(buckets):
            if lines:
                pen = QPen(_with_alpha(col, top * (0.45 + 0.275 * k)), width)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLines(lines)

    # ── the parts that never change shape, drawn once ─────────────────────────
    def _layer(self, dpr: float) -> tuple[QPixmap, QPainter]:
        pm = QPixmap(max(1, int(self._box.width() * dpr)), max(1, int(self._box.height() * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)
        lp = QPainter(pm)
        lp.setRenderHint(QPainter.RenderHint.Antialiasing)
        lp.translate(-self._box.left(), -self._box.top())
        return pm, lp

    def _build_layers(self, cx, cy, r, main, dpr) -> None:
        self._box = QRectF(cx - r * 2.1, cy - r * 1.3, r * 4.2, r * 3.4)

        pm, p = self._layer(dpr)
        fx, fy, _, _ = self._project(np.array([[0.0], [_FLOOR_Y], [0.0]]), cx, cy, r)
        fx, fy = float(fx[0]), float(fy[0])
        # the lit holographic disc of the platform
        p.save()
        p.translate(fx, fy)
        p.scale(1.0, math.sin(_PITCH) * 1.25)
        glow_r = r * 1.3
        g = QRadialGradient(0, 0, glow_r)
        g.setColorAt(0.00, _with_alpha(QColor("#00e5ff"), 0.24))
        g.setColorAt(0.38, _with_alpha(QColor("#6366f1"), 0.12))
        g.setColorAt(1.00, _with_alpha(QColor("#6366f1"), 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(0, 0), glow_r, glow_r)
        p.restore()
        # its concentric iridescent rings
        for rr, a, w, col_hex in (
            (1.20, 0.55, 1.4, "#00e5ff"),
            (1.02, 0.35, 1.0, "#6366f1"),
            (0.74, 0.42, 1.2, "#c084fc"),
            (0.46, 0.25, 1.0, "#00e5ff"),
        ):
            pts = self._ring * rr
            pts[1] += _FLOOR_Y
            X, Y, Z, _ = self._project(pts, cx, cy, r)
            c = QColor(col_hex)
            self._cued(p, X, Y, Z, c, a, a * 0.75, w, "back")
            self._cued(p, X, Y, Z, c, a, a * 0.75, w, "front")
        p.end()
        self._under = pm

    # ── frame ─────────────────────────────────────────────────────────────────
    def paint(self, p: QPainter, cx: float, cy: float, r: float, main: QColor, acc: QColor,
              white: QColor, amp: float, live: bool, name: str = "") -> None:
        spin = self.spin
        amp = max(0.0, min(1.0, amp))
        dev = p.device()
        dpr = float(dev.devicePixelRatioF()) if dev is not None else 1.0
        key = (round(cx), round(cy), round(r, 1), main.rgba(), dpr)
        if key != self._cache_key or self._under is None:
            self._build_layers(cx, cy, r, main, dpr)
            self._cache_key = key

        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.drawPixmap(self._box.topLeft(), self._under)

        # spectrum ticks on the platform rim: the voice, standing up off the floor
        n_t = 64
        ang = np.linspace(0, 2 * math.pi, n_t, endpoint=False) + spin * 0.25
        wob = 0.5 + 0.5 * np.sin(ang * 5.0 + spin * 6.0) * np.cos(ang * 3.0 - spin * 2.3)
        h = 0.03 + (0.20 * amp * wob if live else 0.0)
        base = np.vstack([np.cos(ang) * 1.20, np.full(n_t, _FLOOR_Y), np.sin(ang) * 1.20])
        tip = base.copy()
        tip[1] += h
        bX, bY, bZ, _ = self._project(base, cx, cy, r)
        tX, tY, _, _ = self._project(tip, cx, cy, r)
        bXl, bYl, tXl, tYl = bX.tolist(), bY.tolist(), tX.tolist(), tY.tolist()
        front = (bZ >= 0).tolist()
        col_t = acc if live else main
        for want, a in ((False, 0.25), (True, 0.65)):
            lines = [QLineF(bXl[i], bYl[i], tXl[i], tYl[i]) for i in range(n_t) if front[i] == want]
            if lines:
                p.setPen(QPen(_with_alpha(col_t, a * (0.5 + amp)), 1.4))
                p.drawLines(lines)

        # light beam from the platform up into the core: bright on its axis,
        # fading to nothing at its sides and towards the top
        fx, fy, _, _ = self._project(np.array([[0.0], [_FLOOR_Y], [0.0]]), cx, cy, r)
        fx, fy = float(fx[0]), float(fy[0])
        beam_w = r * 0.30
        top = cy - r * 0.05
        hg = QLinearGradient(fx - beam_w, 0, fx + beam_w, 0)
        hg.setColorAt(0.0, _with_alpha(main, 0.0))
        hg.setColorAt(0.5, _with_alpha(main, 0.16 + 0.22 * amp))
        hg.setColorAt(1.0, _with_alpha(main, 0.0))
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(hg))
        steps, hgt = 8, fy - top
        for k in range(steps):
            p.setOpacity(((k + 1) / steps) ** 1.6)
            p.drawRect(QRectF(fx - beam_w, top + hgt * k / steps, beam_w * 2, hgt / steps + 0.5))
        p.restore()

        # ── Gyroscope and Orbit Rings (Apple Siri & Perplexity Depth System) ──
        siri_violet = QColor("#c084fc")
        siri_cyan   = QColor("#00f0ff")
        siri_indigo = QColor("#6366f1")
        siri_pink   = QColor("#ec4899")

        rings = (
            (self._project(_ry(spin * 0.9) @ _rz(math.radians(64)) @ (self._ring * 0.90), cx, cy, r),
             siri_violet if live else acc, 0.88, 1.8),
            (self._project(_ry(-spin * 1.25) @ _rx(math.radians(58)) @ (self._ring * 0.78), cx, cy, r),
             siri_cyan, 0.76, 1.5),
            (self._project(self._ring * 1.08, cx, cy, r), siri_indigo, 0.58, 1.2),
        )

        # Draw the back half of the 3D gyroscope rings behind the glowing orb
        for (X, Y, Z, _s), col, a, w in rings:
            self._cued(p, X, Y, Z, col, a, a * 0.55, w, "back")

        # ── Apple Siri & Perplexity Iridescent Luminous Nebula Aura ───────────
        sr = r * _SPHERE * (1.0 + 0.08 * amp)
        aura_r = sr * (1.92 + 0.42 * amp + 0.06 * math.sin(spin * 2.8))
        aura = QRadialGradient(QPointF(cx, cy), aura_r)
        aura.setColorAt(0.00, _with_alpha(white, 0.88 + 0.12 * amp))
        aura.setColorAt(0.20, _with_alpha(siri_violet if live else siri_cyan, 0.65 + 0.25 * amp))
        aura.setColorAt(0.45, _with_alpha(siri_cyan, 0.40 + 0.20 * amp))
        aura.setColorAt(0.72, _with_alpha(siri_indigo, 0.18))
        aura.setColorAt(0.90, _with_alpha(siri_pink, 0.08 * (1.0 + amp)))
        aura.setColorAt(1.00, _with_alpha(siri_indigo, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(aura))
        p.drawEllipse(QPointF(cx, cy), aura_r, aura_r)

        # ── Siri Fluid Iridescent Plasma Sphere (Dynamic Swirling Highlight) ──
        rot_ang = spin * 1.6
        hx = cx + sr * 0.32 * math.cos(rot_ang)
        hy = cy + sr * 0.32 * math.sin(rot_ang)
        shade = QRadialGradient(QPointF(cx, cy), sr, QPointF(hx, hy))
        shade.setColorAt(0.00, _with_alpha(white, 0.98))
        shade.setColorAt(0.18, _with_alpha(siri_cyan, 0.90 + 0.10 * amp))
        shade.setColorAt(0.44, _with_alpha(siri_violet, 0.78 + 0.18 * amp))
        shade.setColorAt(0.72, _with_alpha(siri_indigo, 0.45))
        shade.setColorAt(0.92, _with_alpha(siri_pink, 0.28))
        shade.setColorAt(1.00, _with_alpha(siri_cyan, 0.20))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(shade))
        p.drawEllipse(QPointF(cx, cy), sr, sr)

        # Crisp luminous iridescent rim
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(_with_alpha(siri_cyan, 0.85 + 0.15 * amp), 1.6))
        p.drawEllipse(QPointF(cx, cy), sr, sr)

        # ── Siri Luminous Core Star Heart ─────────────────────────────────────
        hr = sr * (0.30 + 0.25 * amp) * (2.1 + 0.15 * math.sin(spin * 3.6))
        heart = QRadialGradient(cx, cy, hr)
        heart.setColorAt(0.00, _with_alpha(white, 1.0))
        heart.setColorAt(0.24, _with_alpha(siri_violet if live else siri_cyan, 0.92))
        heart.setColorAt(0.55, _with_alpha(siri_indigo, 0.50))
        heart.setColorAt(0.85, _with_alpha(siri_pink, 0.22))
        heart.setColorAt(1.00, _with_alpha(siri_cyan, 0.0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(heart))
        p.drawEllipse(QPointF(cx, cy), hr, hr)

        # Draw the front half of the 3D gyroscope rings passing in front of the orb
        for (X, Y, Z, _s), col, a, w in rings:
            self._cued(p, X, Y, Z, col, a, a * 0.55, w, "front")

        # ── Celestial Tracers riding the Equatorial Orbit Ring ────────────────
        (X, Y, Z, _s), _c, _a, _w = rings[2]
        p.setPen(Qt.PenStyle.NoPen)
        for k in range(3):
            i = int((k * _N_RING / 3 + spin * 7.0) % _N_RING)
            depth = float(Z[i])
            rad = (2.4 + 1.8 * max(0.0, depth)) * 3
            x, y = float(X[i]), float(Y[i])
            tg = QRadialGradient(x, y, rad)
            tg.setColorAt(0.0, _with_alpha(white, 0.95 if depth >= 0 else 0.40))
            tg.setColorAt(0.35, _with_alpha(siri_violet if depth >= 0 else siri_cyan, 0.7 if depth >= 0 else 0.25))
            tg.setColorAt(1.0, _with_alpha(siri_indigo, 0.0))
            p.setBrush(QBrush(tg))
            p.drawEllipse(QPointF(x, y), rad, rad)

        # ── Perplexity Cosmic Stardust Particle Field (Drifting Motes) ────────
        a = np.array([ph + spin * sp for _r0, ph, _y, sp in self._motes])
        r0 = np.array([m[0] for m in self._motes])
        pts = np.vstack([np.cos(a) * r0, np.array([m[2] for m in self._motes]), np.sin(a) * r0])
        MX, MY, MZ, _ = self._project(pts, cx, cy, r)
        mote_cols = (siri_cyan, siri_violet, QColor("#fbbf24"), white)
        for idx, (x, y, d) in enumerate(zip(MX.tolist(), MY.tolist(), MZ.tolist())):
            d = max(0.0, d)
            m_col = mote_cols[idx % len(mote_cols)]
            m_rad = (1.2 + 1.2 * d) * (1.0 + 0.3 * amp)
            p.setBrush(QBrush(_with_alpha(m_col, 0.35 + 0.50 * d)))
            p.drawEllipse(QPointF(x, y), m_rad, m_rad)

        # the name, standing on the front edge of the platform
        if name:
            nx, ny, _, _ = self._project(np.array([[0.0], [_FLOOR_Y], [1.2]]), cx, cy, r)
            f = QFont()
            f.setFamilies(_DISPLAY)
            px = max(10, int(r * 0.11))
            f.setPixelSize(px)
            f.setWeight(QFont.Weight.Light)
            f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, max(2.0, round(r * 0.035)))
            p.setFont(f)
            p.setPen(QPen(_with_alpha(white, 0.78 + 0.2 * min(1.0, amp * 2))))
            p.drawText(QRectF(cx - r * 1.6, float(ny[0]) + r * 0.10, r * 3.2, px * 1.8),
                       Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, name)
        p.restore()
