/*
 * Meridian Tilt Sensor Monitor
 * DFR0028 Gravity Digital Tilt Sensor (single-direction, 4x)
 * Powered by 4.5V button cell holders (FIT0337)
 *
 * Wire format (matches Meridian MERIDIAN,* protocol):
 *   MERIDIAN,TILT,<sensor_id>,<state>,<event>
 *
 *   sensor_id : 1–4
 *   state     : UPRIGHT or TILTED
 *   event     : CHANGED or STEADY
 *
 * Examples:
 *   MERIDIAN,TILT,1,UPRIGHT,STEADY      <- sensor 1 upright, no change (heartbeat)
 *   MERIDIAN,TILT,2,TILTED,CHANGED      <- sensor 2 just tipped over (bottle picked up/moved)
 *   MERIDIAN,TILT,2,UPRIGHT,CHANGED     <- sensor 2 returned to upright
 *
 * Heartbeat lines are sent every HEARTBEAT_INTERVAL_MS.
 * CHANGED events are sent immediately on state transition.
 *
 * Sensor wiring (DFR0028, digital interface):
 *   VCC  -> 5V (or 3.3V)
 *   GND  -> GND
 *   SIG  -> Digital pin (see SENSOR_PINS below)
 *
 * The DFR0028 single-direction sensor outputs HIGH when upright (ball contacts pins),
 * LOW when tilted past threshold.
 *
 * NOTE: The 4.5V battery holders power the sensors independently in deployment.
 * During development, use the Arduino 5V rail.
 */

// ── Pin assignments ────────────────────────────────────────────────────────────
// Assign one digital pin per sensor. Use pins with internal pull-up support.
// Avoid pins 0/1 (used by Serial TX/RX on Uno/Nano).
const int SENSOR_PINS[1] = {2};
const int SENSOR_COUNT = 1;

// ── Behavior tuning ───────────────────────────────────────────────────────────
// Debounce: ignore state flickers shorter than this (ms).
// DFR0028 ball can rattle briefly on disturbance — 80ms works well.
const unsigned long DEBOUNCE_MS = 80;

// Heartbeat: send current state for all sensors this often even if nothing changed.
// Lets the kiosk detect serial silence (sensor offline) vs. no events.
const unsigned long HEARTBEAT_INTERVAL_MS = 10000;  // 10 seconds

// ── State tracking ────────────────────────────────────────────────────────────
bool lastStable[4];          // last confirmed (debounced) state per sensor
bool pendingState[4];        // state currently being debounced
unsigned long pendingAt[4];  // millis() when the pending state was first seen
unsigned long lastHeartbeat; // millis() of last heartbeat send

void setup() {
  Serial.begin(9600);
  for (int i = 0; i < SENSOR_COUNT; i++) {
    pinMode(SENSOR_PINS[i], INPUT_PULLUP);
    // Read initial state — HIGH = upright for DFR0028 single-direction
    bool reading = digitalRead(SENSOR_PINS[i]) == HIGH;
    lastStable[i] = reading;
    pendingState[i] = reading;
    pendingAt[i] = 0;
  }
  lastHeartbeat = millis();

  // Send startup message so the host knows the Arduino is live
  Serial.println("MERIDIAN,TILT,INIT,READY");
}

void loop() {
  // Debug mode: print raw pin state continuously to validate wiring quickly.
  for (int i = 0; i < SENSOR_COUNT; i++) {
    int raw = digitalRead(SENSOR_PINS[i]);
    Serial.print("DEBUG,TILT,");
    Serial.print(i + 1);
    Serial.print(",PIN=");
    Serial.print(SENSOR_PINS[i]);
    Serial.print(",RAW=");
    Serial.println(raw == HIGH ? "HIGH" : "LOW");
  }
  delay(300);
}

// ── Output ────────────────────────────────────────────────────────────────────
void emitLine(int sensorId, bool upright, bool changed) {
  // Format: MERIDIAN,TILT,<id>,<UPRIGHT|TILTED>,<CHANGED|STEADY>
  Serial.print("MERIDIAN,TILT,");
  Serial.print(sensorId);
  Serial.print(",");
  Serial.print(upright ? "UPRIGHT" : "TILTED");
  Serial.print(",");
  Serial.println(changed ? "CHANGED" : "STEADY");
}
