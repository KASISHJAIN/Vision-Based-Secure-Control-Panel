Vision-Based Secure Control Panel

Design & Behavior Specification

1. Project Overview

The Vision-Based Secure Control Panel is a gesture-controlled security system that uses computer vision 
to detect hand gestures via a webcam and translates those gestures into secure system commands executed 
on a microcontroller (Arduino).

The goal of this project is to explore human–computer interaction (HCI) by replacing traditional physical 
inputs (buttons, keypads) with intentional hand gestures, while maintaining system safety through state-based 
logic and strict command validation.

This system emphasizes:

* Intentional interaction (no accidental triggers)
* Clear and enforceable system states
* Real-time visual and audio feedback
* Robust hardware–software integration
* Fail-safe design (hardware authority over software)

---

2. High-Level Architecture

Components

1. Python (Vision Layer)

   * Uses OpenCV for real-time webcam frame capture
   * Uses MediaPipe Hands to extract 21 hand landmarks
   * Classifies gestures using rule-based geometric logic
   * Applies gesture stability gating (multi-frame confirmation)
   * Applies cooldown timing to prevent command spamming
   * Enforces one-command-per-gesture behavior
   * Sends validated commands to Arduino over serial
   * Receives and logs acknowledgements from Arduino

Python acts as a non-authoritative advisor. It suggests actions but does not enforce system behavior.

2. Arduino (Control Layer)

The Arduino is the authoritative control and safety layer.

   * Implements a finite state machine (FSM)
   * Maintains the current system state
   * Tracks alert cause (TRIP vs PANIC)
   * Receives newline-terminated commands over serial
   * Validates commands against the current state
   * Applies only legal state transitions
   * Ignores invalid or unsafe commands
   * Controls LEDs and buzzer for real-time feedback
   * Sends structured acknowledgements back to Python

Even if Python fails, misclassifies, or crashes, the Arduino continues to enforce safety.

Communication

* Serial (USB)
* Baud rate: `115200`
* Line-based protocol (`COMMAND\n`)
* Bidirectional (Python → Arduino, Arduino → Python)
   * Python → Arduino (commands)
   * Arduino → Python (status + acknowledgements)

---

3. Design Philosophy

3.1 State-Driven System (Why States Matter)

Instead of reacting directly to gestures, the system operates as a finite state machine (FSM).
This prevents invalid or dangerous transitions.

A gesture alone does nothing unless it is:

* Detected consistently
* Stable across multiple frames
* Allowed in the current state
* Explicitly mapped to a valid command

This mirrors real security systems where:

* You cannot trip an unarmed system
* Alerts must be explicitly cleared
* Emergency overrides always work
* Illegal inputs are ignored, not acted upon

---

4. System States

The system operates as a finite state machine (FSM) with three core states.

| State  | Description                                                                    |
|------- |--------------------------------------------------------------------------------|
| ACTIVE | System is powered on and monitoring, but not armed. This is the default state. |
| ARMED  | System is armed and capable of triggering an alert.                            |
| ALERT  | A critical event or emergency has been detected.                               |

The system starts in ACTIVE rather than IDLE to reflect real-world security systems,
which are typically always running but not necessarily armed.

State transitions are strictly controlled and only occur via valid commands.

---

5. Gestures and Meanings

Detected Gestures (Vision Layer)

| Gesture                      | Description             | Intent                   | Command |
| ---------------------------- | ----------------------- | ------------------------ | ------- |
| Open Palm                    | All fingers extended    | Clear / return to normal | DISARM  |
| Fist                         | All fingers folded      | Arm system               | ARM     |
| Point (Index)                | Index extended only     | Trip system              | TRIP    |
| Panic (Two-Finger Point)     | Index + Middle extended | Emergency override       | PANIC   |

All gestures must be:

* Detected consistently for `N` frames
* Stable
* Not overlapping higher-priority gestures

---

6. Gesture → Command Mapping

| Stable Gesture | Command Sent       |
| -------------- | ------------------ |
| Open Palm      | `DISARM` |
| Fist           | `ARM`              |
| Point          | `TRIP`             |
| Panic          | `PANIC`            |

---

7. Command Priority Rules

Priority matters.
Some gestures override others.

Highest → Lowest:

1. PANIC
2. FIST
3. POINT
4. OPEN
5. NONE

This ensures emergency gestures are never ignored.

---

8. State Transition Logic

Transition Table

| Current State | ARM     | DISARM  | TRIP    | PANIC |
| ------------- | ------- | ------- | ------- | ----- |
| ACTIVE        | ARMED   | ACTIVE  | Ignored | ALERT |
| ARMED         | ARMED   | ACTIVE  | ALERT   | ALERT |
| ALERT         | Ignored | ACTIVE  | Ignored | ALERT |

Key Rules

* PANIC always forces ALERT (override)
* TRIP only works when ARMED
* DISARM always returns to ACTIVE
* Commands sent in invalid states are ignored

---

9. Stability & Safety Mechanisms (Python Side)

To prevent noise and accidental triggers:

9.1 Stability Gating

* A gesture must be detected for `N = 6` consecutive frames
* Counters reset when gesture changes

9.2 Cooldown

* Minimum time between command sends (`~350ms`)
* Prevents spamming the Arduino

9.3 Command Change Check

* Same command is not resent continuously
* Commands only sent when stable gesture changes

---

10. Serial Protocol

From Python → Arduino

```
ARM\n
DISARM\n
TRIP\n
PANIC\n
```

From Arduino → Python

```
READY
RX: ARM
ACK: ACTIVE->ARMED
ACK: ARMED->ALERT (cause=TRIP)
IGNORED (state=0)
```

Terminology

* RX: Arduino received a command
* ACK: Command accepted and applied
* IGNORED: Command rejected due to invalid state

---

11. Emergency Override (Panic Gesture)

The panic gesture is intentionally designed to:

* Require a deliberate hand pose
* Bypass all state restrictions
* Immediately force the system into ALERT

This mirrors real-world panic buttons used in security systems.

---

12. Embedded Hardware Feedback (Arduino Implementation)

The Arduino provides layered real-time feedback using three outputs:

  12.1 RGB LED (State Indicator)

  | State  | Behavior                                   |
  | ------ | ------------------------------------------ |
  | ACTIVE | Solid green                                |
  | ARMED  | Solid amber (red + green)                  |
  | ALERT  | Blinking red (rate depends on alert cause) |

  12.2 White LED (Attention / Monitoring Layer)
  | State  | Behavior                               |
  | ------ | -------------------------------------- |
  | ACTIVE | Off                                    |
  | ARMED  | Heartbeat pulse (monitoring indicator) |
  | ALERT  | Strobe (faster for PANIC alerts)       |

  12.3 Active Buzzer (Urgency & Cause Encoding)
  Because the buzzer is active (ON/OFF only), urgency is encoded using rhythm:
  | Scenario        | Pattern                                |
  | --------------- | -------------------------------------- |
  | ARM event       | Single short chirp                     |
  | ALERT via TRIP  | Continuous alarm cadence               |
  | ALERT via PANIC | Distinct multi-beep pattern with pause |

  12.4 Non-Blocking Embedded Design

   * All LED and buzzer patterns use millis() timing
   * No blocking delays are used
   * Serial communication remains responsive at all times
   * Pattern state resets on every state transition


13. Current Limitations (Known & Accepted)

* Gesture detection is orientation-dependent (y-axis based)
* Rotated or sideways hands may misclassify gestures
* Single-hand support only

These limitations are intentional at this stage to keep debugging focused.

---

14. Future Improvements

* Angle-based finger detection
* Multi-hand support
* Python-side state synchronization
* Logging and replay
* Authentication gestures
* Timeout-based auto-reset from ALERT
* Entry-delay alarm behavior

---

15. Summary

This project is not just gesture detection—it is a stateful, safety-aware control system.

Key takeaways:

* Gestures ≠ actions
* States define legality
* Hardware enforces safety
* Panic always wins
* Vision is filtered before hardware reacts

This design makes the system:

* Predictable
* Safe
* Extensible
* Realistic

---

GESTURE SPECIFICATION
Gesture Definitions

✋ OPEN (Open Palm)

    Physical meaning: “Clear / safe / normal”

    Visual definition:

        All four fingers extended

        Fingertips above PIP joints

        Palm facing camera

    Command: *DISARM*

    State effects:

        ARMED → ACTIVE

        ALERT → ACTIVE

        ACTIVE → stays ACTIVE

    Real-world analogy:
    Disarming or clearing an alarm.

✊ FIST

    Physical meaning: “Lock / secure / arm”

    Visual definition:

        All fingers folded

        Fingertips near MCP joints

        Tips below PIP joints

    Command: *ARM*

    State effects:

        ACTIVE → ARMED

        ARMED → stays ARMED

        ALERT → ignored

    Why this makes sense:
    A closed fist is deliberate and intentional.

☝️ POINT (Index Only)

    Physical meaning: “Trigger / confirm / select”

    Visual definition:

        Index finger extended

        Middle, ring, pinky folded

    Command: *TRIP*

    State effects:

        ARMED → ALERT

        ACTIVE → ignored

        ALERT → ignored

    Key idea:
    Pointing does nothing unless the system is already armed.

✌️ PANIC (Two-Finger Point)

    Physical meaning: “Emergency override”

    Visual definition:

        Index and middle extended

        Ring and pinky folded

        Very distinct from normal pointing

    Command: *PANIC*

    State effects:

      ANY STATE → ALERT

    Why this exists:
    Emergency input must:

        Be fast

        Be unmistakable

        Ignore state restrictions
