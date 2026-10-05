// ==============================================================================
// CardioTwin v4.1 — Dual-Core FreeRTOS Telemetry Firmware for ESP32 + MAX30102
// ==============================================================================
// Architecture (Phase 2 of CardioTwin v4.1 Engineering Plan):
// - Core 1: sampleTask (Priority 5, Real-Time)
//   Strict 100 Hz (10 ms) acquisition via esp_timer_get_time() + vTaskDelayUntil.
//   Thread-safe ring buffer push; zero HTTP or network calls on this core.
// - Core 0: networkTask (Priority 1, Background)
//   Pulls completed 50-sample chunks from FreeRTOS queue; formats JSON payload;
//   sends async keep-alive HTTP POST with microsecond timing deltas.
// - OLED: Low-priority display update (~8 FPS) on Core 1 background.
// ==============================================================================

#include <Wire.h>
#include "MAX30105.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <U8g2lib.h>
#include "esp_timer.h"

// ============================================================
// OLED (SH1106)
// ============================================================
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(
  U8G2_R0,
  U8X8_PIN_NONE
);

// ============================================================
// WiFi & Server Configuration
// ============================================================
const char* ssid       = "YOUR_WIFI_SSID";
const char* password   = "YOUR_WIFI_PASSWORD";

const char* serverIP   = "192.168.1.100"; // Local WiFi workstation IP (update to match your machine's LAN IP)
const int   serverPort = 5000;

const int CHUNK_SIZE = 50;
#define QUEUE_CAPACITY 10

// ============================================================
// Data Structures for Decoupled Telemetry
// ============================================================
struct PpgChunk {
  uint32_t sequence;
  uint64_t first_sample_ms;
  uint32_t sample_count;
  uint32_t dropped_buffers;
  float    device_bpm;
  long     values[CHUNK_SIZE];
  uint32_t deltas_us[CHUNK_SIZE];
};

QueueHandle_t chunkQueue = NULL;
String bootId = "";

// ============================================================
// Sensor & State
// ============================================================
MAX30105 particleSensor;

volatile bool isRunning = false;
volatile long irValue   = 0;
volatile float bpm      = 0.0f;

// Graph & Peak State
#define GRAPH_LEN 128
#define GRAPH_Y   12
#define GRAPH_H   40

long rawGraph[GRAPH_LEN];
int  gIdx  = 0;
bool gFull = false;

unsigned long lastPeakMs = 0;
long peakThresh = 0;
bool aboveThresh = false;
#define BPM_ALPHA 0.2

// URLs
String commandURL;
String dataURL;

// ============================================================
// FORWARD DECLARATIONS
// ============================================================
void sampleTask(void* pvParameters);
void networkTask(void* pvParameters);
void detectBPM(long ir, unsigned long now);
void drawOLED();
void showMessage(const char* title, const char* msg);
void pollCommand();
void sendChunkHttp(const PpgChunk& chunk);

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  // Initialize random boot identifier for restart auditing
  bootId = String("esp32-") + String((uint32_t)esp_random(), HEX);

  // OLED Initialization
  u8g2.begin();
  u8g2.setBusClock(400000);
  showMessage("CardioTwin v4.1", "Booting RTOS...");

  // MAX30102 Sensor Initialization
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 NOT FOUND");
    showMessage("MAX30102", "NOT FOUND");
    while (1) { delay(1000); }
  }

  // 60 = 6.0 mA LED current, 1 sample avg, Red+IR, 100 Hz, 411 us pulse width, 4096 ADC range
  particleSensor.setup(
    60,
    1,
    2,
    100,
    411,
    4096
  );
  Serial.println("MAX30102 READY");

  // Init graph array
  for (int i = 0; i < GRAPH_LEN; i++) {
    rawGraph[i] = 0;
  }

  // WiFi Connection
  showMessage("WiFi", "Connecting...");
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected: " + WiFi.localIP().toString());
  showMessage("WiFi OK", WiFi.localIP().toString().c_str());
  delay(800);

  commandURL = String("http://") + serverIP + ":" + serverPort + "/command";
  dataURL    = String("http://") + serverIP + ":" + serverPort + "/data";

  // Create FreeRTOS Queue for decoupled telemetry transmission
  chunkQueue = xQueueCreate(QUEUE_CAPACITY, sizeof(PpgChunk));
  if (chunkQueue == NULL) {
    Serial.println("Error creating chunkQueue!");
    while (1);
  }

  // Pin high-priority Real-Time Sampling Task to Core 1
  xTaskCreatePinnedToCore(
    sampleTask,
    "SampleTask",
    4096,
    NULL,
    5, // High priority
    NULL,
    1  // Core 1
  );

  // Pin lower-priority Asynchronous Network Task to Core 0
  xTaskCreatePinnedToCore(
    networkTask,
    "NetworkTask",
    8192,
    NULL,
    1, // Low priority
    NULL,
    0  // Core 0
  );

  Serial.println("[+] FreeRTOS Dual-Core Tasks Spawned Successfully.");
}

// ============================================================
// MAIN LOOP: OLED REFRESH ONLY (Core 1 Background)
// ============================================================
void loop() {
  // Smooth OLED refresh at ~8 FPS (120ms)
  drawOLED();
  delay(120);
}

// ============================================================
// CORE 1: REAL-TIME SAMPLING TASK (100 Hz, Ring-Buffer Push)
// ============================================================
void sampleTask(void* pvParameters) {
  TickType_t xLastWakeTime = xTaskGetTickCount();
  const TickType_t xFrequency = pdMS_TO_TICKS(10); // 10 ms = 100 Hz

  uint64_t lastSampleTimeUs = esp_timer_get_time();
  PpgChunk currentChunk;
  int sampleIdx = 0;
  uint32_t chunkSeq = 0;
  uint32_t droppedCount = 0;

  while (true) {
    vTaskDelayUntil(&xLastWakeTime, xFrequency);

    uint64_t nowUs = esp_timer_get_time();
    uint32_t deltaUs = (uint32_t)(nowUs - lastSampleTimeUs);
    lastSampleTimeUs = nowUs;
    unsigned long nowMs = millis();

    long currentRawIr = particleSensor.getIR();
    irValue = currentRawIr;

    // Rolling graph updates for local OLED
    rawGraph[gIdx] = currentRawIr;
    gIdx = (gIdx + 1) % GRAPH_LEN;
    if (gIdx == 0) gFull = true;

    detectBPM(currentRawIr, nowMs);

    if (isRunning) {
      if (sampleIdx == 0) {
        chunkSeq++;
        currentChunk.sequence = chunkSeq;
        currentChunk.first_sample_ms = nowMs;
        currentChunk.dropped_buffers = droppedCount;
      }

      currentChunk.values[sampleIdx] = currentRawIr;
      currentChunk.deltas_us[sampleIdx] = deltaUs;
      sampleIdx++;

      if (sampleIdx >= CHUNK_SIZE) {
        currentChunk.sample_count = CHUNK_SIZE;
        currentChunk.device_bpm = (irValue > 50000 && bpm > 0) ? bpm : 0.0f;

        // Non-blocking queue send: if queue is full, increment dropped count
        if (chunkQueue != NULL) {
          if (xQueueSend(chunkQueue, &currentChunk, 0) != pdTRUE) {
            droppedCount++;
          }
        }
        sampleIdx = 0;
      }
    } else {
      sampleIdx = 0;
    }
  }
}

// ============================================================
// CORE 0: ASYNCHRONOUS NETWORK TASK (HTTP POST & Command Polling)
// ============================================================
void networkTask(void* pvParameters) {
  PpgChunk chunk;
  unsigned long lastPollMs = 0;

  while (true) {
    // Receive chunks ready for transmission with 80ms timeout
    if (xQueueReceive(chunkQueue, &chunk, pdMS_TO_TICKS(80)) == pdTRUE) {
      if (WiFi.status() == WL_CONNECTED) {
        sendChunkHttp(chunk);
      }
    } else {
      // Idle period: Poll server command every 1000 ms when not streaming
      unsigned long nowMs = millis();
      if (!isRunning && (nowMs - lastPollMs >= 1000)) {
        lastPollMs = nowMs;
        if (WiFi.status() == WL_CONNECTED) {
          pollCommand();
        }
      }
    }
  }
}

// ============================================================
// ASYNC HTTP TRANSMISSION (Runs on Core 0)
// ============================================================
void sendChunkHttp(const PpgChunk& chunk) {
  static HTTPClient dataHttp;
  static bool dataHttpOpen = false;

  if (!dataHttpOpen) {
    dataHttp.begin(dataURL);
    dataHttp.setReuse(true);
    dataHttp.setTimeout(800);
    dataHttp.addHeader("Content-Type", "application/json");
    dataHttp.addHeader("Connection", "keep-alive");
    dataHttpOpen = true;
  }

  // Construct payload with real microsecond deltas, sequence, and boot id
  String json = "{\"device_id\":\"cardiotwin-esp32-01\",\"device_boot_id\":\"" + bootId +
                "\",\"firmware_version\":\"4.1.0\",\"sequence\":" + String(chunk.sequence) +
                ",\"first_sample_ms\":" + String(chunk.first_sample_ms) +
                ",\"sample_interval_us\":10000,\"dropped_buffers\":" + String(chunk.dropped_buffers) +
                ",\"timing_deltas_us\":[";
  for (int i = 0; i < CHUNK_SIZE; i++) {
    json += String(chunk.deltas_us[i]);
    if (i < CHUNK_SIZE - 1) json += ",";
  }
  json += "],\"values\":[";
  for (int i = 0; i < CHUNK_SIZE; i++) {
    json += String(chunk.values[i]);
    if (i < CHUNK_SIZE - 1) json += ",";
  }
  json += "]";

  if (chunk.device_bpm > 0) {
    json += ",\"device_bpm\":" + String(round(chunk.device_bpm * 10.0) / 10.0, 1);
  } else {
    json += ",\"device_bpm\":null";
  }
  json += "}";

  int code = dataHttp.POST(json);

  if (code == 200) {
    String resp = dataHttp.getString();
    if (resp.length() > 0) {
      DynamicJsonDocument doc(128);
      if (deserializeJson(doc, resp) == DeserializationError::Ok) {
        if (doc.containsKey("run")) {
          bool serverRun = doc["run"];
          if (serverRun != isRunning) {
            isRunning = serverRun;
            Serial.println(isRunning ? "[+] STREAM STARTED" : "[-] STREAM STOPPED");
          }
        }
      }
    }
  } else {
    dataHttp.end();
    dataHttpOpen = false;
  }
}

// ============================================================
// COMMAND POLLING (Runs on Core 0)
// ============================================================
void pollCommand() {
  HTTPClient http;
  http.begin(commandURL);
  http.setTimeout(800);

  int code = http.GET();
  if (code == 200) {
    String resp = http.getString();
    DynamicJsonDocument doc(128);
    if (deserializeJson(doc, resp) == DeserializationError::Ok) {
      bool serverRun = doc["run"];
      if (serverRun != isRunning) {
        isRunning = serverRun;
        Serial.println(isRunning ? "[+] SERVER STARTED STREAM" : "[-] SERVER STOPPED STREAM");
      }
    }
  }
  http.end();
}

// ============================================================
// PEAK & BPM DETECTION
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
        bpm = bpm * (1 - BPM_ALPHA) + newBpm * BPM_ALPHA;
      }
    }
    lastPeakMs = now;
  } else if (ir < peakThresh) {
    aboveThresh = false;
  }
}

// ============================================================
// OLED DISPLAY RENDERING
// ============================================================
void drawOLED() {
  u8g2.clearBuffer();
  bool fingerOn = irValue > 50000;

  // Header status
  u8g2.setFont(u8g2_font_5x7_tr);
  u8g2.drawStr(0, 8, isRunning ? "* STREAMING" : "IDLE (READY)");

  char bpmText[24];
  if (fingerOn && bpm > 0) {
    sprintf(bpmText, "BPM: %d", (int)round(bpm));
  } else {
    sprintf(bpmText, "BPM: --");
  }
  u8g2.drawStr(72, 8, bpmText);

  // Dynamic PPG waveform plot
  long minVal = rawGraph[0];
  long maxVal = rawGraph[0];
  int len = gFull ? GRAPH_LEN : gIdx;

  for (int i = 0; i < len; i++) {
    if (rawGraph[i] < minVal) minVal = rawGraph[i];
    if (rawGraph[i] > maxVal) maxVal = rawGraph[i];
  }

  long range = maxVal - minVal;
  if (range < 500) range = 500;

  int prevY = -1;
  for (int x = 0; x < len - 1; x++) {
    int idx = gFull ? (gIdx + x) % GRAPH_LEN : x;
    int y = GRAPH_Y + GRAPH_H - (int)(((rawGraph[idx] - minVal) * GRAPH_H) / range);
    y = constrain(y, GRAPH_Y, GRAPH_Y + GRAPH_H);
    if (prevY != -1) {
      u8g2.drawLine(x, prevY, x + 1, y);
    }
    prevY = y;
  }

  // Footer status bar
  u8g2.setFont(u8g2_font_4x6_tr);
  if (!fingerOn) {
    u8g2.drawStr(0, 62, "PLACE FINGER FIRMLY ON SENSOR");
  } else {
    u8g2.drawStr(0, 62, isRunning ? "100Hz RTOS DUAL-CORE TELEMETRY" : "READY TO SAMPLE BASELINE");
  }

  u8g2.sendBuffer();
}

void showMessage(const char* title, const char* msg) {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_6x10_tr);
  u8g2.drawStr(0, 18, title);
  u8g2.setFont(u8g2_font_5x7_tr);
  u8g2.drawStr(0, 38, msg);
  u8g2.sendBuffer();
}