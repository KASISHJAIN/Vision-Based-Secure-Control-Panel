/*
  Vision-Based Secure Control Panel — Arduino Control Layer (FULL SKETCH)

  Hardware (common cathode RGB assumed):
    R_PIN -> D12 (through resistor)
    G_PIN -> D11 (through resistor)
    B_PIN -> D10 (through resistor)
    WHITE_LED -> D6 (through resistor)
    BUZZER -> D5 (active buzzer, + to pin, - to GND)

  Serial protocol (115200 baud, newline-terminated):
    ARM\n, DISARM\n, TRIP\n, PANIC\n

  States:
    ACTIVE (default), ARMED, ALERT
  Alert causes:
    TRIP vs PANIC (changes patterns)

  Notes:
    - Active buzzer: only ON/OFF (patterns are rhythms, not tones).
    - If your RGB is COMMON ANODE, you must invert setRGB() logic.
*/

enum State { ACTIVE = 0, ARMED = 1, ALERT = 2 };
enum AlertCause { CAUSE_NONE = 0, CAUSE_TRIP = 1, CAUSE_PANIC = 2 };

State state = ACTIVE;
AlertCause cause = CAUSE_NONE;

// ---------------- Pins ----------------
const int R_PIN = 12;
const int G_PIN = 11;
const int B_PIN = 10;

const int WHITE_LED = 6;
const int BUZZER = 5;

// ---------------- Timing Config ----------------
// ARMED heartbeat (white LED)
const unsigned long HEARTBEAT_PERIOD = 2000; // ms
const unsigned long HEARTBEAT_ON     = 80;   // ms

// RGB ALERT blink timings
const unsigned long TRIP_RGB_ON   = 300;
const unsigned long TRIP_RGB_OFF  = 300;
const unsigned long PANIC_RGB_ON  = 150;
const unsigned long PANIC_RGB_OFF = 150;

// White ALERT strobe timings
const unsigned long TRIP_WHITE_ON   = 100;
const unsigned long TRIP_WHITE_OFF  = 100;
const unsigned long PANIC_WHITE_ON  = 70;
const unsigned long PANIC_WHITE_OFF = 70;

// Buzzer patterns
const unsigned long TRIP_BUZZ_ON   = 200;
const unsigned long TRIP_BUZZ_OFF  = 200;

// Panic buzzer: 3 quick beeps then pause
const unsigned long PANIC_BEEP_ON    = 100;
const unsigned long PANIC_BEEP_OFF   = 100;
const unsigned long PANIC_PAUSE_OFF  = 700;
const int PANIC_BEEPS = 3;

// One-shot chirp when arming
const unsigned long ARM_CHIRP_MS = 100;
bool armChirpPending = false;
unsigned long armChirpStart = 0;

// ---------------- Pattern State ----------------
struct TogglePattern {
  unsigned long last = 0;
  bool on = false;
};

TogglePattern rgbPat;
TogglePattern whitePat;
TogglePattern tripBuzz;

struct PanicBuzzerPattern {
  unsigned long last = 0;
  bool on = false;
  int beepCount = 0;
  bool inPause = false;
  unsigned long pauseStart = 0;
};

PanicBuzzerPattern panicBuzz;

// ---------------- Low-level pin helpers ----------------
// COMMON CATHODE RGB: HIGH = ON
// If COMMON ANODE: invert outputs (LOW = ON). See comment below.
void setRGB(bool r, bool g, bool b) {
  digitalWrite(R_PIN, r ? HIGH : LOW);
  digitalWrite(G_PIN, g ? HIGH : LOW);
  digitalWrite(B_PIN, b ? HIGH : LOW);

  /*
    If your RGB is COMMON ANODE, use this instead:

    digitalWrite(R_PIN, r ? LOW : HIGH);
    digitalWrite(G_PIN, g ? LOW : HIGH);
    digitalWrite(B_PIN, b ? LOW : HIGH);
  */
}

void setWhite(bool on) {
  digitalWrite(WHITE_LED, on ? HIGH : LOW);
}

void setBuzzer(bool on) {
  digitalWrite(BUZZER, on ? HIGH : LOW);
}

// Reset all pattern players so transitions are clean and predictable
void resetPatterns() {
  rgbPat = {};
  whitePat = {};
  tripBuzz = {};
  panicBuzz = {};
  armChirpPending = false;
}

// Central transition function (single source of truth)
void transitionTo(State nextState, AlertCause nextCause) {
  State prev = state;
  state = nextState;
  cause = nextCause;

  // Reset pattern phases on every state change or cause change
  resetPatterns();

  // Schedule an arm chirp only when entering ARMED from ACTIVE
  if (prev == ACTIVE && state == ARMED) {
    armChirpPending = true;
    armChirpStart = millis();
  }
}

// ---------------- Effects Layer ----------------
void updateRGB(unsigned long now) {
  if (state == ACTIVE) {
    // Solid green
    setRGB(false, true, false);
    return;
  }

  if (state == ARMED) {
    // Solid amber/yellow
    setRGB(true, true, false);
    return;
  }

  // ALERT
  unsigned long onMs  = (cause == CAUSE_PANIC) ? PANIC_RGB_ON  : TRIP_RGB_ON;
  unsigned long offMs = (cause == CAUSE_PANIC) ? PANIC_RGB_OFF : TRIP_RGB_OFF;
  unsigned long interval = rgbPat.on ? onMs : offMs;

  if (now - rgbPat.last >= interval) {
    rgbPat.last = now;
    rgbPat.on = !rgbPat.on;
  }

  // Red blink
  setRGB(rgbPat.on, false, false);
}

void updateWhite(unsigned long now) {
  if (state == ACTIVE) {
    setWhite(false);
    return;
  }

  if (state == ARMED) {
    // Heartbeat using modulo phase (no extra state needed)
    unsigned long phase = now % HEARTBEAT_PERIOD;
    setWhite(phase < HEARTBEAT_ON);
    return;
  }

  // ALERT strobe (rate depends on cause)
  unsigned long onMs  = (cause == CAUSE_PANIC) ? PANIC_WHITE_ON  : TRIP_WHITE_ON;
  unsigned long offMs = (cause == CAUSE_PANIC) ? PANIC_WHITE_OFF : TRIP_WHITE_OFF;
  unsigned long interval = whitePat.on ? onMs : offMs;

  if (now - whitePat.last >= interval) {
    whitePat.last = now;
    whitePat.on = !whitePat.on;
  }

  setWhite(whitePat.on);
}

void updateBuzzer(unsigned long now) {
  if (state == ACTIVE) {
    setBuzzer(false);
    return;
  }

  if (state == ARMED) {
    // One-shot chirp when arming
    if (armChirpPending) {
      if (now - armChirpStart <= ARM_CHIRP_MS) {
        setBuzzer(true);
      } else {
        setBuzzer(false);
        armChirpPending = false;
      }
    } else {
      setBuzzer(false);
    }
    return;
  }

  // ALERT
  if (cause == CAUSE_TRIP) {
    // Simple repeating beep
    unsigned long interval = tripBuzz.on ? TRIP_BUZZ_ON : TRIP_BUZZ_OFF;
    if (now - tripBuzz.last >= interval) {
      tripBuzz.last = now;
      tripBuzz.on = !tripBuzz.on;
    }
    setBuzzer(tripBuzz.on);
    return;
  }

  // PANIC pattern: 3 quick beeps then pause
  // State machine:
  //  - If inPause: buzzer off until pause duration elapsed
  //  - Else: toggle on/off using 100/100; count completed "on" beeps
  if (panicBuzz.inPause) {
    setBuzzer(false);
    if (now - panicBuzz.pauseStart >= PANIC_PAUSE_OFF) {
      panicBuzz.inPause = false;
      panicBuzz.beepCount = 0;
      panicBuzz.on = false;
      panicBuzz.last = now;
    }
    return;
  }

  unsigned long interval = panicBuzz.on ? PANIC_BEEP_ON : PANIC_BEEP_OFF;
  if (now - panicBuzz.last >= interval) {
    panicBuzz.last = now;

    // When we are about to turn OFF, that completes one beep (ON segment finished)
    if (panicBuzz.on == true) {
      panicBuzz.beepCount++;
    }

    panicBuzz.on = !panicBuzz.on;

    // After N beeps, enter pause (ensure buzzer goes OFF)
    if (panicBuzz.beepCount >= PANIC_BEEPS) {
      panicBuzz.inPause = true;
      panicBuzz.pauseStart = now;
      panicBuzz.on = false;
    }
  }

  setBuzzer(panicBuzz.on);
}

void updateEffects(unsigned long now) {
  updateRGB(now);
  updateWhite(now);
  updateBuzzer(now);
}

// ---------------- Serial / Control Layer ----------------
void ack(const __FlashStringHelper* msg) {
  Serial.println(msg);
}

void handleCommand(const String& cmd) {
  Serial.print("RX: ");
  Serial.println(cmd);

  // PANIC always forces ALERT
  if (cmd == "PANIC") {
    transitionTo(ALERT, CAUSE_PANIC);
    ack(F("ACK: ANY->ALERT (cause=PANIC)"));
    return;
  }

  // DISARM always returns to ACTIVE and clears cause
  if (cmd == "DISARM") {
    transitionTo(ACTIVE, CAUSE_NONE);
    ack(F("ACK: ANY->ACTIVE"));
    return;
  }

  // ARM: only from ACTIVE (ARMED->ARMED is allowed noop)
  if (cmd == "ARM") {
    if (state == ACTIVE) {
      transitionTo(ARMED, CAUSE_NONE);
      ack(F("ACK: ACTIVE->ARMED"));
    } else if (state == ARMED) {
      ack(F("ACK: ARM (noop)"));
    } else {
      ack(F("IGNORED (in ALERT)"));
    }
    return;
  }

  // TRIP: only from ARMED
  if (cmd == "TRIP") {
    if (state == ARMED) {
      transitionTo(ALERT, CAUSE_TRIP);
      ack(F("ACK: ARMED->ALERT (cause=TRIP)"));
    } else {
      Serial.print("IGNORED (state=");
      Serial.print((int)state);
      Serial.println(")");
    }
    return;
  }

  ack(F("IGNORED (unknown cmd)"));
}

void handleSerialNonBlocking() {
  if (!Serial.available()) return;

  // Read one line command (newline terminated)
  String cmd = Serial.readStringUntil('\n');
  cmd.trim();
  if (cmd.length() == 0) return;

  handleCommand(cmd);
}

// ---------------- Arduino setup/loop ----------------
void setup() {
  pinMode(R_PIN, OUTPUT);
  pinMode(G_PIN, OUTPUT);
  pinMode(B_PIN, OUTPUT);
  pinMode(WHITE_LED, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  setRGB(false, false, false);
  setWhite(false);
  setBuzzer(false);

  Serial.begin(115200);
  delay(2000); // allow serial monitor / python to connect after reset
  Serial.println("READY");

  // Start in ACTIVE
  transitionTo(ACTIVE, CAUSE_NONE);
}

void loop() {
  unsigned long now = millis();

  // Effects run continuously and never block
  updateEffects(now);

  // Read + apply serial commands without blocking
  handleSerialNonBlocking();
}
