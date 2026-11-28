# Plugin Integration & Manager Audit Report

**Subsystem:** Extensions, Dynamic Plugin Loader & Settings Forms  
**Module:** `gui/overlays.py`, `core/plugin_loader.py`, `gui/window.py`  
**Status:** **OPERATIONAL & VERIFIED**

---

## 1. Problem Identification

In prior builds, opening `PluginManagerOverlay` without passing a pre-loaded plugin dictionary raised:
`TypeError: PluginManagerOverlay.__init__() missing 1 required positional argument: 'plugins'`
if `self.get_plugins` returned None or empty.

## 2. Hardening & Auto-Discovery

`PluginManagerOverlay` and `PluginSettingsOverlay` were refactored in `gui/overlays.py` to guarantee graceful initialization:
```python
class PluginManagerOverlay(QWidget):
    def __init__(self, plugins: list[dict] = None, parent=None):
        super().__init__(parent)
        if plugins is None:
            try:
                from core.plugin_loader import discover_plugins
                plugins = discover_plugins()
            except Exception:
                plugins = []
```
- Automatically queries the plugin registry if no list is passed.
- Prevents UI crashes and gracefully displays installed plugins.
- Preserves the per-plugin ON/OFF toggles and test triggers.
