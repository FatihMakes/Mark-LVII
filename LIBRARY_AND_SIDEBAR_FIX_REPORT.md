# Library & Sidebar Integration Audit & Repair Report

**Subsystem:** Library, Navigation Sidebar & Secondary Panels  
**Module:** `core/library_manager.py`, `gui/library_overlay.py`, `gui/window.py`, `gui/perplexity_nav.py`  
**Status:** **OPERATIONAL & VERIFIED**

---

## 1. Problem Identification

In prior builds, clicking **Library** on the navigation sidebar exhibited degraded behavior:
- The handler in `gui/window.py` previously performed a superficial existence check for a non-existent reports folder and failed silently.
- There was no dedicated user-facing `LibraryOverlay` dialog, meaning users could not browse stored files, preview reports, or open notes.
- Other secondary sidebar items below Library lacked unified diagnostic tracking and safety fallbacks.

## 2. Implemented Architecture

### Backend: `core/library_manager.py`
- Root path: `~/.jarvis_library/` with standard categorized subfolders:
  - `Documents`, `Reports`, `Notes`, `Projects`, `Spreadsheets`
- **File Management & Ingestion**:
  - `list_files(subfolder, file_type, recursive)`
  - `list_folders()`
  - `search_library(query)` (recursive matching across filenames and text contents)
  - `import_document(source_path, dest_folder)` (safe ingestion with collision handling)
  - `save_note(title, content, folder)` (atomic markdown persistence)
- **Deep Content Extraction**:
  - PyMuPDF for Adobe PDF documents
  - `python-docx` for Microsoft Word documents
  - Python `csv` and `openpyxl` for Excel spreadsheets
  - Standard UTF-8 decoding for markdown, code, and text files
- **macOS System Integration**:
  - `open_in_macos_viewer(file_path)`: Uses native `open -a Preview <file>` for graphics/PDFs and default system association for documents.

### Frontend: `gui/library_overlay.py`
- Centered HUD dialog (`_OW = 860`, `_OH = 580`) styled using JARVIS palette tokens (`C.PANEL2`, `C.BORDER`, `C.PRI`).
- Search input with live text filtering across name, path, and file type.
- Category pills: `All`, `Document`, `Note`, `Spreadsheet`, `Image`, `Code`.
- Two-column split interface:
  - Left: Interactive file list with item count, modification time, and file size badges.
  - Right: Real-time text preview pane, metadata inspector, and action buttons.
- Quick action toolbar:
  - `Open in Preview`: Opens target file in native macOS Preview.app.
  - `New Note`: Opens inline note composer and saves directly into `~/.jarvis_library/Notes/`.
  - `Import File`: macOS file picker for importing local PDFs/spreadsheets.
  - `Delete`: Safe file deletion with confirmation prompt.

## 3. Sidebar Wiring in `gui/window.py`
All sidebar actions are now connected to active overlays:
- `library` $\rightarrow$ `_open_library_panel()`
- `memory` $\rightarrow$ `_open_memory_panel()`
- `identity` $\rightarrow$ `_open_identity_panel()`
- `voice_lab` $\rightarrow$ `_open_voice_lab_panel()`
- `speakers` $\rightarrow$ `_open_speakers_panel()`
- `local_ai` $\rightarrow$ `_open_local_ai_panel()`
- `companion` $\rightarrow$ `_open_companion_panel()`
- `privacy` $\rightarrow$ `_open_privacy_panel()`
- `plugins` $\rightarrow$ `_open_plugin_manager()`
- `remote` $\rightarrow$ `_open_remote()`
- `diagnostics` $\rightarrow$ `_open_diagnostics_panel()`
- `settings` $\rightarrow$ `_toggle_drawer()`
- `tasks` $\rightarrow$ Switches `_context_panel` to Tab 3 (Tasks & Routines).
