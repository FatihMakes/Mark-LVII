# JARVIS H3.2 — Anime Entertainment & ani-cli Integration Report

---

## 1. Overview & Capabilities

Adapted from reference repository `pystardust/ani-cli`, the anime subsystem delivers comprehensive voice and text-controlled streaming, episode discovery, sub/dub switching, and local watch history directly on macOS.

### Key Capabilities:
- **Title Search:** Instantaneous lookup across verified anime metadata catalogs (Naruto, One Piece, Bleach, Attack on Titan, Jujutsu Kaisen, Demon Slayer, Death Note) combined with live HiAnime scraping.
- **Episode Selection:** Supports specific episode playback (e.g. *"Naruto episode 5 chalao"*), season arc breakdowns, and latest episode listings.
- **Sub / Dub Toggle:** Supports original Japanese with English subtitles (`Sub`) or English dubbed versions (`Dub`).
- **Media Player Integration:** Auto-detects and integrates with macOS media players:
  - `/Applications/IINA.app/Contents/MacOS/iina-cli` (macOS native modern player)
  - `/usr/local/bin/mpv` (Unix vector video player)
  - `/Applications/VLC.app`
- **Watch History:** Persists recent anime, last episode viewed, audio mode, and timestamp in `memory/anime_history.json`. Supports one-phrase resumption (*"Continue anime"* / *"Anime aage chalao"*).
- **Multi-Lingual Voice Parsing:** High-accuracy regex parser supporting English, Hindi, and Hinglish.

---

## 2. Architecture & Components

```
[Voice / Text Command]
          │
          ▼
actions/anime_control.py (Tool declaration & PyQt thread-safe player dispatch)
          │
          ▼
core/anime_controller.py (AnimeController singleton)
     ├── parse_voice_command(text)
     ├── search(query, limit)
     ├── get_episodes(anime_title)
     ├── play_anime(title, episode, dub, quality)
     │       └── Subprocess: bin/ani-cli (Detached async background process)
     └── continue_watching() & get_history()
             └── memory/anime_history.json
```

---

## 3. Immediate Test Scenario 2 Verification

**Query:** *"JARVIS, search Naruto and show me available episodes."*  
**Execution:**
```python
from actions.anime_control import anime_control_handler
res = anime_control_handler({'query': 'search Naruto and show me available episodes'})
```
**Output Returned:**
> *"Naruto has 220 episodes available. Status is Finished. Would you like me to start episode 1 or a specific episode?"*

**HUD Panel Stamped:**
- Title: `Naruto`
- Status: `Finished`
- Available Episodes: `220`
- Seasons:
  - Part 1: Genin Arc (Episodes 1-52)
  - Part 2: Chunin Exam Arc (Episodes 53-100)
  - Part 3: Sasuke Recovery (Episodes 101-135)
  - Part 4: Fillers (Episodes 136-220)

All 8 tests in `tests/test_h3_2_anime.py` pass cleanly.
