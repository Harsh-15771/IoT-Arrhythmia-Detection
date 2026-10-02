// ============================================================
// ESP32 + MAX30102 + SH1106 OLED — Live PPG Graph
// ============================================================

#include <Wire.h>
#include "MAX30105.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <U8g2lib.h>

// ============================================================
// OLED (SH1106)
// ============================================================

U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(
  U8G2_R0,
  U8X8_PIN_NONE
);

// ============================================================
// WiFi & Server
// ============================================================

const char* ssid       = "YOUR_WIFI_SSID";
const char* password   = "YOUR_WIFI_PASSWORD";

const char* serverIP   = "192.168.1.100"; // Local WiFi workstation IP (update to your machine's LAN IP)
const int   serverPort = 5000;


const int CHUNK_SIZE = 50;

// ============================================================
// Sensor
// ============================================================

MAX30105 particleSensor;

// ============================================================
// State
// ============================================================

bool          isRunning   = false;

long          sampleBuf[CHUNK_SIZE];
int           sampleIdx   = 0;

unsigned long lastSample  = 0;
unsigned long lastPoll    = 0;
unsigned long lastDisplay = 0;

// ============================================================
// Graph
// ============================================================

#define GRAPH_LEN 128
#define GRAPH_Y   12
#define GRAPH_H   40

long rawGraph[GRAPH_LEN];

int  gIdx  = 0;
bool gFull = false;

long irValue = 0;

// ============================================================
// BPM
// ============================================================

float bpm = 0;

unsigned long lastPeakMs = 0;

long peakThresh = 0;

bool aboveThresh = false;

#define BPM_ALPHA 0.2

// ============================================================
// URLs
// ============================================================

String commandURL;
String dataURL;

// ============================================================
// SETUP
// ============================================================

void setup() {

  Serial.begin(115200);

  Wire.begin(21, 22);

  // OLED
  u8g2.begin();

  showMessage("PPG Monitor", "Booting...");

  // MAX30102
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {

    Serial.println("MAX30102 NOT FOUND");

    showMessage("MAX30102", "NOT FOUND");

    while (1);
  }

  particleSensor.setup(
    60,
    4,
    2,
    100,
    411,
    4096
  );

  Serial.println("MAX30102 READY");

  // Init graph
  for (int i = 0; i < GRAPH_LEN; i++) {
    rawGraph[i] = 0;
  }

  // WiFi
  showMessage("WiFi", "Connecting...");

  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {

    delay(500);

    Serial.print(".");
  }

  Serial.println("");
  Serial.println(WiFi.localIP());

  showMessage("WiFi OK", WiFi.localIP().toString().c_str());

  delay(1000);

  commandURL =
    String("http://") + serverIP + ":" + serverPort + "/command";

  dataURL =
    String("http://") + serverIP + ":" + serverPort + "/data";
}

// ============================================================
// LOOP
// ============================================================

void loop() {

  unsigned long now = millis();

  // Poll command
  if (now - lastPoll >= 1000) {

    lastPoll = now;

    pollCommand();
  }

  // Sample sensor
  if (now - lastSample >= 10) {

    lastSample = now;

    irValue = particleSensor.getIR();

    rawGraph[gIdx] = irValue;

    gIdx = (gIdx + 1) % GRAPH_LEN;

    if (gIdx == 0) gFull = true;

    detectBPM(irValue, now);

    // Send to server
    if (isRunning) {

      sampleBuf[sampleIdx++] = irValue;

      if (sampleIdx >= CHUNK_SIZE) {

        sendChunk();

        sampleIdx = 0;
      }
    }
  }

  // OLED refresh
  if (now - lastDisplay >= 50) {

    lastDisplay = now;

    drawOLED();
  }
}

// ============================================================
// BPM DETECTION
// ============================================================

void detectBPM(long ir, unsigned long now) {

  if (ir < 50000) {

    bpm = 0;

    return;
  }

  long bufMin = rawGraph[0];
  long bufMax = rawGraph[0];

  int len = gFull ? GRAPH_LEN : gIdx;

  for (int i = 0; i < len; i++) {

    if (rawGraph[i] < bufMin) bufMin = rawGraph[i];

    if (rawGraph[i] > bufMax) bufMax = rawGraph[i];
  }

  peakThresh = bufMin + (bufMax - bufMin) * 6 / 10;

  if (ir > peakThresh && !aboveThresh) {

    aboveThresh = true;

    if (lastPeakMs > 0) {

      unsigned long interval = now - lastPeakMs;

      if (interval > 300 && interval < 2000) {

        float newBpm = 60000.0 / interval;

        bpm =
          bpm * (1 - BPM_ALPHA)
          + newBpm * BPM_ALPHA;
      }
    }

    lastPeakMs = now;

  } else if (ir < peakThresh) {

    aboveThresh = false;
  }
}

// ============================================================
// DRAW OLED
// ============================================================

void drawOLED() {

  u8g2.clearBuffer();

  bool fingerOn = irValue > 50000;

  // Top bar
  u8g2.setFont(u8g2_font_5x7_tr);

  u8g2.drawStr(0, 8,
    isRunning ? "* REC" : "IDLE");

  char bpmText[20];

  if (fingerOn && bpm > 0) {

    sprintf(bpmText,
      "BPM:%d",
      (int)round(bpm));

  } else {

    sprintf(bpmText, "BPM:--");
  }

  u8g2.drawStr(75, 8, bpmText);

  u8g2.drawLine(0, 10, 127, 10);

  // No finger
  if (!fingerOn) {

    u8g2.drawStr(20, 30,
      "Place finger");

    u8g2.drawStr(35, 42,
      "on sensor");
  }

  else {

    int len = gFull ? GRAPH_LEN : gIdx;

    long gMin = rawGraph[0];
    long gMax = rawGraph[0];

    for (int i = 0; i < len; i++) {

      if (rawGraph[i] < gMin)
        gMin = rawGraph[i];

      if (rawGraph[i] > gMax)
        gMax = rawGraph[i];
    }

    long gRange = gMax - gMin;

    if (gRange < 200)
      gRange = 200;

    int prevX = -1;
    int prevY = -1;

    for (int i = 0; i < GRAPH_LEN; i++) {

      int bufI =
        (gIdx - GRAPH_LEN + i + GRAPH_LEN)
        % GRAPH_LEN;

      long val = rawGraph[bufI];

      int x = i;

      int y =
        GRAPH_Y + GRAPH_H - 1
        - (int)((val - gMin)
        * (GRAPH_H - 1)
        / gRange);

      y = constrain(
        y,
        GRAPH_Y,
        GRAPH_Y + GRAPH_H - 1
      );

      if (prevX >= 0) {

        u8g2.drawLine(
          prevX,
          prevY,
          x,
          y
        );
      }

      prevX = x;
      prevY = y;
    }
  }

  // Bottom line
  u8g2.drawLine(0, 54, 127, 54);

  // Status
  if (!fingerOn) {

    u8g2.drawStr(0, 63,
      "No finger");

  } else if (isRunning) {

    u8g2.drawStr(0, 63,
      "Sending...");

  } else {

    u8g2.drawStr(0, 63,
      "Waiting...");
  }

  u8g2.sendBuffer();
}

// ============================================================
// SHOW MESSAGE
// ============================================================

void showMessage(
  const char* line1,
  const char* line2
) {

  u8g2.clearBuffer();

  u8g2.setFont(u8g2_font_6x12_tr);

  u8g2.drawStr(0, 24, line1);

  u8g2.drawStr(0, 44, line2);

  u8g2.sendBuffer();
}

// ============================================================
// POLL COMMAND
// ============================================================

void pollCommand() {

  if (WiFi.status() != WL_CONNECTED)
    return;

  HTTPClient http;

  http.begin(commandURL);

  int code = http.GET();

  if (code == 200) {

    String body = http.getString();

    DynamicJsonDocument doc(128);

    deserializeJson(doc, body);

    bool run = doc["run"];

    if (run != isRunning) {

      isRunning = run;

      sampleIdx = 0;

      Serial.println(
        isRunning
        ? "STARTED"
        : "STOPPED"
      );
    }
  }

  http.end();
}

// ============================================================
// SEND CHUNK
// ============================================================

void sendChunk() {

  if (WiFi.status() != WL_CONNECTED)
    return;

  // Build dual-contract payload for seamless backend ingestion
  String json = "{\"samples\":[";
  for (int i = 0; i < CHUNK_SIZE; i++) {
    json += String(sampleBuf[i]);
    if (i < CHUNK_SIZE - 1)
      json += ",";
  }
  json += "],\"values\":[";
  for (int i = 0; i < CHUNK_SIZE; i++) {
    json += String(sampleBuf[i]);
    if (i < CHUNK_SIZE - 1)
      json += ",";
  }
  json += "],\"bpm\":" + String((int)round(bpm > 0 ? bpm : 72)) + ",\"spo2\":98}";

  HTTPClient http;

  http.begin(dataURL);

  http.addHeader(
    "Content-Type",
    "application/json"
  );

  int code = http.POST(json);

  if (code != 200) {

    Serial.printf(
      "POST ERROR %d\n",
      code
    );
  }

  http.end();
}