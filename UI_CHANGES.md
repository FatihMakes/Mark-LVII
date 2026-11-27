# UI_CHANGES.md — Mark-LI UI fixes

Scope: `/home/user/ui.py` (the new Mark-LI UI). All changes were applied to the
working copy, re-verified with `py_compile` and a full offscreen PyQt6 harness,
and the two required screenshots were regenerated offscreen.

---

## (1) BUG — content panel placed off-screen at y=728 in a 720px window

**Root cause.** `ContentPanel._slide_up()` and `MainWindow.resizeEvent()`
positioned the slide-up card relative to the *central widget* using a fraction
of its height (`H - int(H*0.42) - margin`), and the panel was created as a child
of `central` but never clamped; combined with a stale/odd metric the card ended
up at `y=728` — below the 720px-tall window, i.e. completely off-screen.

**Fix.** The card is now anchored inside the **centre orb column** and clamped:

* New `MainWindow.content_card_rect() -> QRectF` computes the target rect:
  anchored to the centre widget (`self._center`, the orb column) with **16px
  margins**, **height ~260px** (clamped to `H - 2*margin`), sitting **above the
  waveform / bottom of the orb column**.
* The rect is explicitly clamped so the card always lies **fully inside the
  central widget** (x/y forced on-screen, width capped to `W - x`, height
  capped to `H`).
* `ContentPanel._target_rect()` asks the window for that rect (falling back to
  an internal 16px/260px computation if the window is unavailable).
* The slide-up animation now animates from just below the card's rest position
to the *clamped* target, so the final geometry is always valid.
* `MainWindow._show_content()` repositions the panel **before** showing it.
* `MainWindow.resizeEvent()` repositions it **on every resize** via
  `content_card_rect()`.

**Verification.** `content_panel.geometry()` is asserted to lie fully inside
`centralWidget().rect()` both after `present()` and after a resize round-trip;
height is asserted `~260`; `y` is asserted on-screen. All pass.

---

## (2) Setup overlay showing + overlay centring

### Setup overlay was shown because the harness config was invalid

The window shows the setup overlay when `_check_config()` fails, i.e. when
`config/api_keys.json` is missing or lacks `gemini_api_key` / `os_system`.
The screenshot harness therefore writes a **valid temp** `api_keys.json` first:

```json
{ "gemini_api_key": "x", "os_system": "linux" }
```

The harness then asserts the setup overlay is **not** visible and that
`_ready is True`.

### Every overlay is now centred over the central widget and clamped

Added `MainWindow._clamp_overlay(ov)`: it centres the overlay over the central
widget and **clamps** width/height to the central widget and clamps x/y so the
owner can never draw outside the window. It is used by:

* `_show_overlay()` — used by **setup**, **customize**, **plugins**, **remote
  key** and **controls** overlays; and
* the `resizeEvent()` overlay loop (setup, remote, customize, controls,
  plugin-manager).

`SetupOverlay`, `RemoteKeyOverlay`, `CustomizeOverlay`, `PluginManagerOverlay`
and the controls card all flow through `_show_overlay()`, so all five are
centred + clamped.

### Dim backdrop scrim behind modal overlays

`DimBackdrop` (a `rgba(0,0,0,150)` full-central scrim) is shown behind modal
overlays by `_show_overlay()` and hidden again by `_hide_backdrop_if_idle()`
when no modal remains. Verified: backdrop visible with a modal, hidden when
none.

---

## (3) Re-run `py_compile` + full offscreen harness, regenerate 2 screenshots

### `py_compile`

```
python -m py_compile ui.py   ->   rc = 0
```

### Offscreen harness

A full `QT_QPA_PLATFORM=offscreen` harness constructs `JarvisUI`, checks the
palette / accent round-trip / `retheme_all_widgets`, all widget classes, the
content-panel geometry, overlay centring+clamping, and the backdrop:

```
SMOKE   : 28/28 passed
HARNESS2: 17/17 passed   (geometry / overlay / screenshot checks)
```

### Screenshots (offscreen, `win.grab()`)

* `screenshot_cyan.png` — **default cyan theme** (`#00d4ff`), a sample
  conversation in the chat panel and the **metrics strip open**, with **no
  modal** shown.
* `screenshot_orange_content.png` — **orange `#ff6b00` accent**, with the
  **content panel visibly open over the orb area** (fully inside the window).

---

## Files

| File | Purpose |
|------|---------|
| `ui.py` | Patched Mark-LI UI |
| `screenshot_cyan.png` | Cyan theme + conversation + metrics open |
| `screenshot_orange_content.png` | Orange accent + content panel open |
| `UI_CHANGES.md` | This document |
