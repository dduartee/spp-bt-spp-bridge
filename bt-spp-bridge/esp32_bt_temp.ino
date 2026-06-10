/*
 * ESP32 Bluetooth SPP Temperature Sender
 * Sends temperature data every 5 seconds over Bluetooth Serial (SPP).
 * Simulates realistic temperature with smooth oscillation (day/night cycle).
 *
 * Board: ESP32 Dev Module (works on all variants: S2, S3, C3, C6, etc.)
 * No external hardware required.
 *
 * To connect:
 *   Android: Use "Serial Bluetooth Terminal" app
 *   Desktop:  Pair via OS Bluetooth, open COM port
 */

#include <Arduino.h>
#include <BluetoothSerial.h>

// ── Configuration ──────────────────────────────────────────────────
#define BT_DEVICE_NAME    "ESP32-TempSensor"
#define SEND_INTERVAL_MS  5000           // 5 seconds
#define SERIAL_BAUD       115200

// ── Globals ────────────────────────────────────────────────────────
BluetoothSerial SerialBT;

bool      btConnected     = false;
float     currentTemp     = 22.5f;
unsigned long lastSendTime = 0;

// Sine-wave parameters for realistic temperature oscillation
const float TEMP_BASELINE = 24.0f;       // center temperature
const float TEMP_AMPLITUDE = 4.0f;       // ±4 °C swing
const unsigned long TEMP_PERIOD = 86400; // 24-hour cycle in seconds

// ── Bluetooth event handlers ───────────────────────────────────────
// Uses the supported Arduino-ESP32 callback interface

void onBTConnect() {
  btConnected = true;
  Serial.println("[BT] Client connected");
  SerialBT.println("ESP32 Temperature Sensor ready.");
  SerialBT.println("Commands: TEMP?, STATUS, HELP");
}

void onBTDisconnect() {
  btConnected = false;
  Serial.println("[BT] Client disconnected");
}

// ── Temperature simulation ─────────────────────────────────────────
/*
 * Generates a realistic temperature curve:
 *   - Base sine wave (24-hour cycle, simulates day/night)
 *   - Small high-frequency noise (weather-like variation)
 *   - Result clamps to a plausible indoor range [15.0, 35.0]
 */
float readTemperature() {
  unsigned long t = millis() / 1000UL;            // seconds since boot

  // 24-hour sine: peaks at ~6 PM UTC, troughs at ~6 AM
  float dayCycle = sin((float)t * 2.0f * PI / (float)TEMP_PERIOD - PI / 2.0f);

  // High-frequency noise: use LCG pseudo-random seeded by time
  unsigned long seed = (t / 7UL) * 1103515245UL + 12345UL;
  float noise = ((float)(seed % 1000UL) / 1000.0f - 0.5f) * 1.5f;

  float temp = TEMP_BASELINE + TEMP_AMPLITUDE * dayCycle + noise;

  // Clamp
  if (temp < 15.0f) temp = 15.0f;
  if (temp > 35.0f) temp = 35.0f;

  currentTemp = temp;
  return currentTemp;
}

// ── Send formatted temperature packet ──────────────────────────────
void sendTemperaturePacket() {
  unsigned long timestamp = millis() / 1000UL;
  float temp = readTemperature();

  // Use a fixed-size stack buffer — no heap allocation
  char buffer[64];
  snprintf(buffer, sizeof(buffer),
           "TEMP:%.1f\xC2\xB0""C,TS:%lu\r\n",
           temp, timestamp);

  if (btConnected) {
    SerialBT.print(buffer);
    Serial.print("[BT SENT] ");
  } else {
    Serial.print("[LOCAL] ");
  }
  Serial.print(buffer);
}

// ── Handle incoming commands ───────────────────────────────────────
void handleIncomingCommand() {
  String cmd = SerialBT.readStringUntil('\n');
  cmd.trim();

  if (cmd.length() == 0) return; // ignore empty lines

  Serial.print("[BT RECV] ");
  Serial.println(cmd);

  char response[64];

  if (cmd.equalsIgnoreCase("TEMP?")) {
    snprintf(response, sizeof(response), "TEMP:%.1f\xC2\xB0""C\r\n", currentTemp);
    SerialBT.print(response);

  } else if (cmd.equalsIgnoreCase("STATUS")) {
    snprintf(response, sizeof(response),
             "STATUS:Connected,Interval:%d,BTName:%s\r\n",
             SEND_INTERVAL_MS / 1000, BT_DEVICE_NAME);
    SerialBT.print(response);

  } else if (cmd.equalsIgnoreCase("HELP")) {
    SerialBT.print("Commands: TEMP?, STATUS, HELP\r\n");

  } else {
    SerialBT.print("Unknown command. Send HELP for list.\r\n");
  }
}

// ── Periodic alive notification ────────────────────────────────────
// Logs a heartbeat every 60 seconds even without BT connection.
static unsigned long lastHeartbeat = 0;

void heartbeatCheck() {
  unsigned long now = millis();
  if (now - lastHeartbeat >= 60000UL) {
    lastHeartbeat = now;
    Serial.print("[ALIVE] Uptime: ");
    Serial.print(now / 1000UL);
    Serial.print("s, BT: ");
    Serial.println(btConnected ? "Connected" : "Waiting...");
  }
}

// ── Setup ──────────────────────────────────────────────────────────
void setup() {
  Serial.begin(SERIAL_BAUD);
  delay(500);

  Serial.println("\n=== ESP32 Bluetooth SPP Temperature Sender ===");

  // Register callbacks (supported API in Arduino-ESP32)
  SerialBT.onConnect(onBTConnect);
  SerialBT.onDisconnect(onBTDisconnect);

  // Start Bluetooth SPP server
  if (!SerialBT.begin(BT_DEVICE_NAME)) {
    Serial.println("[ERROR] Bluetooth initialization failed! Halting.");
    while (1) { delay(1000); }
  }

  Serial.print("[BT] Device name: \"");
  Serial.print(BT_DEVICE_NAME);
  Serial.println("\"");
  Serial.println("[BT] Waiting for SPP client connection...");

  lastSendTime = millis();
  Serial.println("[OK] Setup complete. Sending every 5 seconds.\n");
}

// ── Main loop ──────────────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  // Temperature transmission (unsigned arithmetic handles wrap safely)
  if (now - lastSendTime >= SEND_INTERVAL_MS) {
    lastSendTime += SEND_INTERVAL_MS;    // avoids drift accumulation
    sendTemperaturePacket();
  }

  // Incoming Bluetooth commands
  if (btConnected && SerialBT.available()) {
    handleIncomingCommand();
  }

  // Heartbeat on hardware serial (no connection watchdog)
  heartbeatCheck();

  delay(10);  // yield to Bluetooth stack
}
