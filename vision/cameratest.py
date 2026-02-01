import cv2              # webcam frames
import time             # FPS + timers
import mediapipe as mp  # landmarks
import serial           # Arduino serial

# ------------------------------ Helper Functions ------------------------------
def dist2(a, b):
    dx = a.x - b.x
    dy = a.y - b.y
    return dx*dx + dy*dy

def is_fist(hand_landmarks, thresh=0.10):
    """
    FIST:
      - fingertips close to MCP joints (distance threshold)
      - fingertips below PIP joints (folded)
    Uses normalized landmark coords, so thresh is in normalized units (~0..1).
    """
    lm = hand_landmarks.landmark
    tips = [lm[8], lm[12], lm[16], lm[20]]       # index, middle, ring, pinky tips
    mcps = [lm[5], lm[9], lm[13], lm[17]]        # MCP joints
    pips = [lm[6], lm[10], lm[14], lm[18]]       # PIP joints

    t2 = thresh * thresh
    close_to_mcp  = all(dist2(tip, mcp) < t2 for tip, mcp in zip(tips, mcps))
    tip_below_pip = all(tip.y > pip.y for tip, pip in zip(tips, pips))
    return close_to_mcp and tip_below_pip

def is_open_palm(hand_landmarks):
    """OPEN: fingertips above PIP joints (extended upward in image coords)."""
    lm = hand_landmarks.landmark
    tips = [lm[8], lm[12], lm[16], lm[20]]
    pips = [lm[6], lm[10], lm[14], lm[18]]
    return all(tip.y < pip.y for tip, pip in zip(tips, pips))

def is_point(hand_landmarks):
    """POINT: index extended; middle/ring/pinky folded."""
    lm = hand_landmarks.landmark
    index_extended = lm[8].y < lm[6].y
    middle_folded  = lm[12].y > lm[10].y
    ring_folded    = lm[16].y > lm[14].y
    pinky_folded   = lm[20].y > lm[18].y
    return index_extended and middle_folded and ring_folded and pinky_folded

def is_panic(hand_landmarks):
    """PANIC: index + middle extended; ring + pinky folded."""
    lm = hand_landmarks.landmark
    index_extended  = lm[8].y < lm[6].y
    middle_extended = lm[12].y < lm[10].y
    ring_folded     = lm[16].y > lm[14].y
    pinky_folded    = lm[20].y > lm[18].y
    return index_extended and middle_extended and ring_folded and pinky_folded

def pick_raw_gesture(hand_landmarks):
    """
    Apply priority rules:
      PANIC > FIST > POINT > OPEN > NONE
    """
    if is_panic(hand_landmarks):
        return "PANIC"
    if is_fist(hand_landmarks):
        return "FIST"
    if is_point(hand_landmarks):
        return "POINT"
    if is_open_palm(hand_landmarks):
        return "OPEN"
    return "NONE"


def main():
    # ---------------- Webcam (Windows: prefer DSHOW) ----------------
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Try changing VideoCapture(0) to (1).")

    # ---------------- MediaPipe ----------------
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    mp_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )

    # ---------------- Serial ----------------
    PORT = "COM6"
    BAUD = 115200
    ser = serial.Serial(PORT, BAUD, timeout=0.1)

    # Arduino Uno resets when serial opens; give it time to reboot.
    time.sleep(2.0)
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    print("Connected to Arduino on", PORT)

    # Read boot messages (READY, etc.)
    boot_deadline = time.time() + 2.5
    while time.time() < boot_deadline:
        if ser.in_waiting:
            line = ser.readline().decode("utf-8", errors="ignore").strip()
            if line:
                print("ARDUINO:", line)

    # ---------------- Gesture mapping ----------------
    gesture_to_cmd = {
        "OPEN":  "DISARM",
        "FIST":  "ARM",
        "POINT": "TRIP",
        "PANIC": "PANIC",
        "NONE":  "NOOP",
    }

    # ---------------- Stability + emission controls ----------------
    N = 6  # frames needed for stable
    raw_prev = "NONE"
    raw_count = 0
    stable_gesture = "NONE"
    stable_prev = "NONE"

    COOLDOWN_SEC = 0.35
    last_send_time = 0.0

    prev_time = time.time()

    try:
        # ---------------- Main loop ----------------
        while True:
            ok, frame = cap.read()
            if (not ok) or (frame is None):
                print("Frame read failed; skipping...")
                # still allow quit
                if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q')):
                    break
                continue

            # ---- Read any Arduino messages without blocking ----
            try:
                while ser.in_waiting:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        print("ARDUINO:", line)
            except serial.SerialException as e:
                print("Serial read error:", e)

            # ---- Vision ----
            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            raw_gesture = "NONE"

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]

                # Draw landmarks
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )

                raw_gesture = pick_raw_gesture(hand_landmarks)

                # ---- Stability gating (single counter) ----
                if raw_gesture == raw_prev:
                    raw_count += 1
                else:
                    raw_prev = raw_gesture
                    raw_count = 1

                if raw_count >= N:
                    stable_gesture = raw_gesture

            else:
                # No hand detected: reset raw tracking and (optionally) stable to NONE
                raw_prev = "NONE"
                raw_count = 0
                stable_gesture = "NONE"

            # ---- Command emission (only when stable changes) ----
            now_t = time.time()
            if stable_gesture != stable_prev:
                cmd = gesture_to_cmd.get(stable_gesture, "NOOP")

                # Only send real commands, rate-limited
                if cmd != "NOOP" and (now_t - last_send_time) >= COOLDOWN_SEC:
                    ser.write((cmd + "\n").encode("utf-8"))
                    print("SENT:", cmd)
                    last_send_time = now_t
                    stable_prev = stable_gesture
                elif cmd == "NOOP":
                    # allow stable_prev to follow NONE so you can re-trigger later
                    stable_prev = stable_gesture
                # else: cooldown blocked; do NOT advance stable_prev,
                # so the command will still send once cooldown passes if you hold the gesture.

            # ---- UI overlay ----
            now = time.time()
            fps = 1.0 / max(now - prev_time, 1e-6)
            prev_time = now

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
            cv2.putText(frame, f"RAW: {raw_gesture} ({raw_count}/{N})", (10, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            cv2.putText(frame, f"STABLE: {stable_gesture}", (10, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2)

            cv2.imshow("Vision-Based Secure Control Panel", frame)

            # Quit
            if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q')):
                break

    finally:
        # ---------------- Cleanup (ALWAYS runs) ----------------
        try:
            hands.close()
        except Exception:
            pass
        try:
            cap.release()
        except Exception:
            pass
        cv2.destroyAllWindows()
        try:
            ser.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
