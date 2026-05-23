/*
  ============================================================
  GATEKEEPER AI — ESP32
  ============================================================
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>

// ─── Wi-Fi ───────────────────────────────────────────────────
const char* WIFI_SSID     = "Wifi_Name";
const char* WIFI_PASSWORD = "Wifi_Password";

// ─── Agent ───────────────────────────────────────────────────
const char* AGENT_HOST = "http://192.168.1.6:5050/check";

// ─── Pins ────────────────────────────────────────────────────
#define PIR_PIN     13
#define BUZZER_PIN  14

// ─── Timing ──────────────────────────────────────────────────
#define DISPLAY_DURATION_MS  20000   // total time to show message
#define SCROLL_INTERVAL_MS    2500   // ms between each vertical scroll step
#define COOLDOWN_MS          10000   // cooldown between triggers

// ─── LCD ─────────────────────────────────────────────────────
LiquidCrystal_I2C lcd(0x27, 16, 2);

// ─── State ───────────────────────────────────────────────────
enum State { STATE_IDLE, STATE_DISPLAYING, STATE_COOLDOWN };
State         currentState    = STATE_IDLE;
unsigned long stateStartMs    = 0;
unsigned long lastCountUpdate = 0;

// ─── Message lines ───────────────────────────────────────────
#define MAX_LINES 16
String        msgLines[MAX_LINES];   // word-wrapped lines
int           lineCount    = 0;
int           scrollTop    = 0;      // index of line shown on row 0
unsigned long lastScrollMs = 0;

// ─── Helpers ─────────────────────────────────────────────────
// Buzzer Helper
void buzzerBeep(int times = 1) {
  if (BUZZER_PIN < 0) return;           // Skip if buzzer disabled
  for (int i = 0; i < times; i++) {
    digitalWrite(BUZZER_PIN, HIGH); delay(120); // Turn buzzer ON
    digitalWrite(BUZZER_PIN, LOW);              // Turn buzzer OFF
    if (i < times - 1) delay(100);      // Small gap between beeps
  }
}

// Change System State
// Resets timer whenever state changes
void setState(State s) {
  currentState = s;
  stateStartMs = millis();
}

// Splits long messages into multiple LCD lines without breaking words whenever possible.
// Maximum LCD width = 16 characters
void buildLines(const String& msg) {
  lineCount = 0;              // Reset line counter
  for (int i = 0; i < MAX_LINES; i++) msgLines[i] = "";   // Clear previous lines

  String remaining = msg;
  remaining.trim();

  while (remaining.length() > 0 && lineCount < MAX_LINES) {   // Continue until message fully processed
    if (remaining.length() <= 16) {
      // Fits entirely — last line
      msgLines[lineCount++] = remaining;
      break;
    }

    // Find the last space at or before position 16
    int breakPos = -1;
    for (int i = 15; i >= 0; i--) {
      if (remaining.charAt(i) == ' ') {
        breakPos = i;
        break;
      }
    }

    if (breakPos == -1) {
      // No space found — force break at 16 (single long word)
      breakPos = 16;
      msgLines[lineCount++] = remaining.substring(0, breakPos);
      remaining = remaining.substring(breakPos);
    } else {
      msgLines[lineCount++] = remaining.substring(0, breakPos);
      remaining = remaining.substring(breakPos + 1);  // skip the space
    }
    remaining.trim();
  }
}

// ── Render the two visible rows from scrollTop ───────────────
void renderRows() {
  lcd.clear();

  // Row 0 — always the scrollTop line
  lcd.setCursor(0, 0);
  if (scrollTop < lineCount) {
    lcd.print(msgLines[scrollTop]);
  }

  // Row 1 — next line if it exists
  lcd.setCursor(0, 1);
  if (scrollTop + 1 < lineCount) {
    lcd.print(msgLines[scrollTop + 1]);
  }
}

// ── Set message, build lines, show first 2 rows ──────────────
void lcdSetMessage(const String& msg) {
  Serial.println("[MSG] " + msg);
  buildLines(msg);      // Convert message into LCD lines
  scrollTop    = 0;     // Reset scrolling
  lastScrollMs = millis();

  Serial.print("[LINES] count=");
  Serial.println(lineCount);
  for (int i = 0; i < lineCount; i++) {
    Serial.println("  [" + String(i) + "] " + msgLines[i]);
  }

  renderRows();
}

// ── Advance vertical scroll by one row ───────────────────────
void updateScroll() {
  // Only scroll if there are more than 2 lines
  if (lineCount <= 2) return;

  unsigned long now = millis();
  if (now - lastScrollMs < SCROLL_INTERVAL_MS) return;
  lastScrollMs = now;

  // Move down one line
  scrollTop++;

  // If we've gone past the last visible pair, loop back to top
  if (scrollTop + 1 >= lineCount) {
    scrollTop = 0;
  }

  renderRows();
}

// ─── WiFi ────────────────────────────────────────────────────
void connectWifi() {
  Serial.print("[WiFi] Connecting to ");
  Serial.println(WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);   // Start WiFi connection
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("Connecting WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED) {   // Wait until connected
    delay(500); Serial.print(".");
    lcd.setCursor(attempts % 16, 1); lcd.print(".");
    attempts++;
    if (attempts > 40) {      // Restart if timeout exceeded
      Serial.println("\n[WiFi] FAILED. Restarting.");
      ESP.restart();
    }
  }
  Serial.println("\n[WiFi] Connected: " + WiFi.localIP().toString());   // Connected successfully
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("WiFi Connection");
  lcd.setCursor(0, 1); lcd.print("Successful!");
  delay(2000);
}

// ─── Call AI Agent ───────────────────────────────────────────
String callAgent() {
  if (WiFi.status() != WL_CONNECTED) connectWifi();     // Reconnect WiFi if disconnected
  HTTPClient http;
  http.begin(AGENT_HOST);         // Begin HTTP request
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(15000);
  int httpCode = http.POST("{\"event\":\"motion_detected\"}");
  String result = "Come back later";
  if (httpCode == 200) {
    DynamicJsonDocument doc(512);
    if (!deserializeJson(doc, http.getString())) {
      result = doc["message"].as<String>();
    }
  } else {
    Serial.println("[HTTP] Error: " + String(httpCode));
    result = "Agent offline";
  }
  http.end();
  return result;
}

// ─── Setup ───────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(500);
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("Gatekeeper AI");
  lcd.setCursor(0, 1); lcd.print("Starting...");
  pinMode(PIR_PIN, INPUT);      // Configure PIR sensor
  if (BUZZER_PIN >= 0) {
    pinMode(BUZZER_PIN, OUTPUT);
    digitalWrite(BUZZER_PIN, LOW);
  }
  delay(2000);
  connectWifi();
  lcd.clear();
  lcd.setCursor(0, 0); lcd.print("Gatekeeper AI");
  lcd.setCursor(0, 1); lcd.print("Ready :)");
  setState(STATE_IDLE);     // Enter idle state
  Serial.println("[GATEKEEPER] Ready.");
}

// ─── Main Loop ───────────────────────────────────────────────
void loop() {
  unsigned long now = millis();

  switch (currentState) {
    // Waiting for motion detection
    case STATE_IDLE:
      if (digitalRead(PIR_PIN) == HIGH) {
        Serial.println("[PIR] Motion detected!");
        buzzerBeep(1);
        lcd.clear();
        lcd.setCursor(0, 0); lcd.print("Hi! One moment");
        lcd.setCursor(0, 1); lcd.print("Checking sched..");
        String msg = callAgent();     // Ask AI agent
        lcdSetMessage(msg);
        buzzerBeep(2);
        setState(STATE_DISPLAYING);
      }
      break;
    // Shows AI response on LCD
    case STATE_DISPLAYING:
      updateScroll();     // Handle scrolling
      if (now - stateStartMs >= DISPLAY_DURATION_MS) {    // Finished display duration
        Serial.println("[STATE] Done. Cooldown.");
        lcd.clear();
        lcd.setCursor(0, 0); lcd.print("Standby...");
        setState(STATE_COOLDOWN);     // Enter cooldown
        lastCountUpdate = 0;
      }
      break;
    // Prevents repeated immediate triggers
    case STATE_COOLDOWN: {
      unsigned long elapsed   = now - stateStartMs;
      unsigned long remaining = (COOLDOWN_MS > elapsed)
                                ? (COOLDOWN_MS - elapsed) / 1000 + 1
                                : 0;
      if (now - lastCountUpdate >= 1000) {  // Update LCD every second
        lastCountUpdate = now;
        lcd.clear();
      }
      if (elapsed >= COOLDOWN_MS) {   // Cooldown complete
        Serial.println("[STATE] Cooldown done. Idle.");
        lcd.clear();
        lcd.setCursor(0, 0); lcd.print("Gatekeeper AI");
        lcd.setCursor(0, 1); lcd.print("Ready :)");
        setState(STATE_IDLE);
      }
      break;
    }
  }
  // Small CPU relief delay
  delay(50);
}
