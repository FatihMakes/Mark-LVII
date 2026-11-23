# JARVIS H3.2 — macOS Deep Scan & File Discovery Report

---

## 1. Capabilities & Scope

Implemented in `core/mac_analyzer.py` and `actions/mac_scan.py`, the deep scanner provides read-only inspection of macOS storage, processes, and hidden artifacts while strictly complying with APFS filesystem semantics and macOS Transparency, Consent, and Control (TCC) security:

1. **System Diagnostics & Health Audit:** Comprehensive snapshot of Apple Silicon unified memory (total, free, used %), CPU load, disk space, active input audio devices, and API service status.
2. **Large File Discovery:** Recursively identifies files larger than 100 MB across user spaces (`~/Downloads`, `~/Desktop`, `~/Documents`, caches), displaying name, size in MB, and last modified date.
3. **Duplicate Detection via SHA-256:** Two-stage duplicate detection (size grouping followed by fast SHA-256 chunk hashing) to find redundant duplicate file clusters without heavy I/O thrashing.
4. **Hidden Dotfile Inspection:** Discovers hidden configuration files and directories (`.DS_Store`, cache directories, temp artifacts).
5. **RAM-Heavy Process Inspector:** Lists top memory-consuming processes using `psutil`, reporting PID, process name, RSS memory in MB, and CPU utilization percentage.
6. **Safe Download Manager (`actions/download_manager.py`):**
   - Safe HTTPS streaming downloads.
   - Confinement to `~/Downloads`.
   - Optional SHA-256 checksum verification.
   - **Hard Rule Enforced:** No automatic or untrusted execution of downloaded files.

---

## 2. Immediate Test Scenario 3 Verification

**Query:** *"JARVIS, run a complete read-only system audit and report all broken features."*  
**Execution:**
```python
from actions.mac_scan import mac_scan_handler
res = mac_scan_handler({'query': 'run a complete read-only system audit and report all broken features'})
```
**Output Returned:**
> *"System audit complete. Memory is 1.6 GB free / 8.0 GB total (80.0% used). Disk is 16.44 GB free of 228.27 GB (43.6% used). ℹ️ Unconfigured services: Google Maps, OpenWeather"*

**HUD Panel Displayed:**
- Timestamp: Real-time scan timestamp
- Memory Metrics: Active RAM free / total / percentage
- CPU: Real core count and utilization
- Disk: APFS volume metrics
- API Services: Verified active keys vs unconfigured services
- Findings: Clean report identifying unconfigured external API keys honestly

All tests in `tests/test_h3_2_filesystem.py` pass.
