# talks to the webcam; handles image frames
import cv2 
# used to calcuate FPS
import time
# pretrained ML pipeline from Google
import mediapipe as mp

#helper functions
def dist2(a, b):
    dx = a.x - b.x
    dy = a.y - b.y
    return dx*dx + dy*dy

#2 conditions
# the tip is close to the mcp
# the tip is below pip
def is_fist(hand_landmarks, thresh=0.10): #within 10% of frame width/height
    lm = hand_landmarks.landmark
    tips = [lm[8], lm[12], lm[16], lm[20]] #index, middle, ring, pinky
    mcps = [lm[5], lm[9], lm[13], lm[17]]
    pips = [lm[6], lm[10], lm[14], lm[18]]

    #comparing distance^2 to thresh^2
    t2 = thresh*thresh

    close_to_mcp = all(dist2(tip, mcp) < t2 for tip, mcp in zip(tips, mcps))
    tip_below_pip = all(tip.y > pip.y for tip, pip in zip(tips, pips))
    return close_to_mcp and tip_below_pip

def is_open_palm(hand_landmarks):
    lm = hand_landmarks.landmark
    tips = [lm[8], lm[12], lm[16], lm[20]]
    pips = [lm[6], lm[10], lm[14], lm[18]]

    return all(tip.y < pip.y for tip, pip in zip(tips, pips))

def is_point(hand_landmarks):
    lm = hand_landmarks.landmark

    index_extended = lm[8].y < lm[6].y

    middle_folded = lm[12].y > lm[10].y
    ring_folded   = lm[16].y > lm[14].y
    pinky_folded  = lm[20].y > lm[18].y

    return index_extended and middle_folded and ring_folded and pinky_folded



def main():
    cap = cv2.VideoCapture(0) # 0 is the default webcam

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    if not cap.isOpened():
        raise RuntimeError("Could not open webcam. Try changing VideoCapture(0) to (1).")
    
    mp_hands = mp.solutions.hands # loads the hands solution (prebuilt pipeline)
    mp_drawing = mp.solutions.drawing_utils
    mp_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        model_complexity=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6
    )
    
    prev_time = time.time()

    stable_gesture = "NONE"
    open_count = 0
    fist_count = 0
    point_count = 0
    N = 5 # frames required to confirm a gesture


    while True:
        ok, frame = cap.read()
        if not ok:
            print("Frame read failed; skipping...")
            continue

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb) #detect/track hand

        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    mp_hands.HAND_CONNECTIONS,
                    mp_styles.get_default_hand_landmarks_style(),
                    mp_styles.get_default_hand_connections_style(),
                )

                lm = hand_landmarks.landmark
                d = dist2(lm[8], lm[5]) ** 0.5  # index tip to index MCP distance
                cv2.putText(
                    frame, 
                    f"d(index): {d:.3f}", 
                    (10, 140), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.8, 
                    (0,0,0),
                    2
                )

                fist = is_fist(hand_landmarks)
                cv2.putText(
                    frame,
                    f"FIST: {fist}",
                    (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0,0,0),
                    2
                )

                open_palm = is_open_palm(hand_landmarks)
                cv2.putText(
                    frame,
                    f"OPEN: {open_palm}",
                    (10, 170),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0,0,0),
                    2
                )

                point = is_point(hand_landmarks)
                cv2.putText(
                    frame,
                    f"POINT: {point}",
                    (10, 210),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0,0,0),
                    2
                )

                if open_palm and not fist:
                    open_count +=1
                else:
                    open_count = 0
                
                if fist and not open_palm:
                    fist_count +=1
                else:
                    fist_count = 0

                if point and not open_palm and not fist:
                    point_count +=1
                else:
                    point_count = 0
                
                if fist_count >= N:
                    stable_gesture = "FIST"
                elif point_count >= N:
                    stable_gesture = "POINT"
                elif open_count >= N:
                    stable_gesture = "OPEN"
                else:
                    stable_gesture = "NONE"

                
                cv2.putText(
                    frame,
                    f"STABLE: {stable_gesture}",
                    (10,240),
                    cv2.FONT_HERSHEY_COMPLEX,
                    0.9,
                    (0,0,0),
                    2
                )
        else:
            open_count = fist_count = point_count = 0
            stable_gesture = "NONE"

        now = time.time()
        fps = 1.0 / max(now - prev_time, 1e-6)
        prev_time = now

        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,0), 2)
        cv2.putText(frame, "Step 1: landmarks only (press Q to quit)", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 2)

        cv2.imshow("Hand Landmarks", frame)
        if cv2.waitKey(1) & 0xFF in (ord('q'), ord('Q')):
            break

    hands.close()
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
        

