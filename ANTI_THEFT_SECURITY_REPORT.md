# JARVIS H3.1 — Anti-Theft Siren Guard Report
**Author:** Aman Kumar ([@iamTechieAman](https://github.com/iamTechieAman))  
**Component:** `core/anti_theft.py` & `actions/anti_theft.py`  
**Status:** FULLY VERIFIED (3/3 Siren Guard Tests Passed)

---

## 1. Objectives & Threat Model

When working in shared workspaces, coffee shops, libraries, or airports, laptops and paired phones are vulnerable to opportunistic theft ("grab-and-run"). 

The H3.1 Anti-Theft Siren Guard protects both the desktop workstation and paired companion mobile devices by monitoring sensor telemetry for physical movement and power cable detachment.

---

## 2. State Machine & Execution Protocol

```
[DISARMED] ── arm() ──> [ARMING (10s Countdown)] ── timer expires ──> [ARMED]
                                                                          │
  ┌────────────────────── disarm(PIN / Owner Voice) ──────────────────────┤
  │                                                                       │ (Sensor Trigger)
  ▼                                                                       ▼
[DISARMED] <── disarm(PIN) ───────────────────────────────────────── [TRIGGERED]
                                                                 (Max Siren Blaring)
```

### 2.1 Arming Protocol & Grace Period
* Triggered via voice command *"JARVIS, arm anti-theft guard"* or HUD button.
* Initiates a **10-second countdown grace period** (`GuardState.ARMING`) allowing the user to place their devices down, close bags, and step away safely without false alarms.
* Once the timer elapses, the system shifts to `GuardState.ARMED`.

### 2.2 Trigger Conditions
* **Charger Disconnection:** Unplugging the MagSafe/USB-C power adapter from the laptop or paired Android phone.
* **Motion / Gyroscope Perturbation:** Sudden displacement of the device while in the armed state.
* **Companion Phone Disconnect:** Loss of companion BLE / Local Wi-Fi beacon while armed.

### 2.3 Emergency Siren Response
Upon sensor breach, the guard immediately shifts to `GuardState.TRIGGERED`:
1. Sets paired Android phone volume to 100% and triggers maximum-frequency emergency audio.
2. Spawns desktop high-decibel alarm audio (`afplay /System/Library/Sounds/Sosumi.aiff`).
3. Disables mute commands and audio ducking.
4. Generates an encrypted security incident record in `memory/theft_incidents.jsonl` recording timestamp, trigger reason, and device identifier.

### 2.4 Disarm Authentication
The alarm CANNOT be silenced by normal mute buttons, volume keys, or keyboard shortcuts. Disarming requires:
* The Owner Master PIN: `1170`.
* Or authenticated Owner Biometric Voice saying: *"JARVIS, disarm alarm with master authorization"*.
* An invalid PIN leaves the siren actively blaring and increments incident violation counters.
* Once disarmed, active siren processes are cleanly terminated and sensors stood down.

---

## 3. Test Verification Results

* `test_19`: Arming enters grace period with `is_armed() == True`. -> **PASS**
* `test_20`: Power disconnect while armed triggers alarm and logs incident. -> **PASS**
* `test_21`: Disarming with wrong PIN fails; disarming with master PIN `1170` silences siren and restores `DISARMED` state. -> **PASS**
