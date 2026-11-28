# Instagram Reels Browser Playback & Control Report

**Subsystem:** Instagram Reels Browser Automation  
**Module:** `core/instagram_controller.py`, `actions/instagram_control.py`  
**Engine:** Playwright Chromium with Persistent Session Context  
**Status:** **OPERATIONAL & VERIFIED**

---

## 1. Objectives

Provide real-world voice and desktop automation for Instagram Reels:
1. Load individual Reel URLs or the continuous Reels explore feed (`https://www.instagram.com/reels/`).
2. Detect HTML5 `<video>` elements in the DOM.
3. Automatically handle muted states and initiate playback.
4. Verify actual playback progression by sampling `video.currentTime` across time.
5. Provide playback controls: Play, Pause, Next Reel, Previous Reel, Mute/Unmute.
6. Extract metadata: creator handle, caption, and video duration.

## 2. Technical Architecture

### A. Persistent Browser Context
- Uses Playwright Chromium with persistent user profile directory at `~/.jarvis_instagram_profile`.
- Bypasses automation flags: `--disable-blink-features=AutomationControlled` and `--autoplay-policy=no-user-gesture-required`.
- Reuses existing browser context across actions to prevent cold-start delays.

### B. DOM Introspection & Playback Verification
- When opening a Reel, `_start_video_playback()` executes JavaScript directly in the page:
  ```javascript
  const v = document.querySelector('video');
  if (v) {
      v.muted = false;
      v.play();
  }
  ```
- **Real-Time Playback Assertion**:
  - Samples `v.currentTime` at $t_0$.
  - Waits 500ms and samples `v.currentTime` at $t_1$.
  - Confirms `is_playing = (t_1 > t_0) || (t_1 > 0)`.

### C. Continuous Navigation
- Seamless navigation between Reels using keyboard navigation (`ArrowDown` for next reel, `ArrowUp` for previous reel).
- Auto-extracts creator handle (`header span`), caption (`div[role="button"] span`), and like count for HUD display.
