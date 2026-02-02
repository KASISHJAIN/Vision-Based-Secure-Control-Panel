# Vision-Based Secure Control Panel

🎥 **Full Hardware + Computer Vision Demo (YouTube, unlisted):**  
https://youtube.com/shorts/-IvRiYe2ZAA

---

## Overview

The Vision-Based Secure Control Panel is a gesture-controlled security system that replaces
traditional physical inputs with intentional hand gestures, while maintaining strict safety
through state-based hardware enforcement.

Computer vision is used for perception, but **all safety-critical logic is enforced on the Arduino**.

---

## Key Features

- Real-time hand gesture recognition using **OpenCV + MediaPipe**
- Finite State Machine (FSM) enforced on Arduino
- Explicit prevention of illegal state transitions
- Panic override gesture that forces ALERT from any state
- Non-blocking LED and buzzer patterns using `millis()`
- Clear separation between perception (Python) and enforcement (hardware)

---

## System Architecture

**Python (Vision Layer)**
- Detects and classifies hand gestures
- Applies stability gating and cooldown logic
- Sends validated commands over serial
- Cannot directly control system state

**Arduino (Control Layer)**
- Authoritative FSM and safety enforcement
- Accepts or ignores commands based on current state
- Controls LEDs and buzzer for real-time feedback
- Remains safe even if vision fails or crashes

---

## States and Gestures (Summary)

- **ACTIVE** → monitoring, not armed  
- **ARMED** → ready to trigger alert  
- **ALERT** → emergency state  

Gestures:
- ✊ Fist → ARM  
- ☝️ Point → TRIP (only when armed)  
- ✋ Open palm → DISARM  
- ✌️ Two fingers → PANIC override  

---

## Documentation

- 📄 **Full Design & Behavior Specification:** [`DESIGN.md`](DESIGN.md)

---

## Tech Stack

- Python, OpenCV, MediaPipe
- Arduino (C++)
- Serial communication (115200 baud)
- RGB LED, white LED, active buzzer
