#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_SHT4x.h>
#include <Adafruit_SGP40.h>
#include <math.h>
#include <stdio.h>

/*
  Air Sensor JSON Stream over HTTP
  - Reads only real sensors we have: SHT41 + SGP40
  - Sends JSON every 1 second
  - JSON payload includes only sensor fields:
      air_temp_c, air_rh_pct, air_voc_raw

  Server endpoint:
    POST /telemetry/air/raw
*/

// ===== WiFi + API config =====
const char* WIFI_SSID = "48 Hunt 2.4";
const char* WIFI_PASS = "gooner41";
const char* API_HOST = "192.168.1.218";  // laptop/server IP
const int API_PORT = 8001;
const char* API_PATH = "/telemetry/air";

static const uint32_t SEND_EVERY_MS = 1000;
uint32_t last_send_ms = 0;

Adafruit_SHT4x sht4;
Adafruit_SGP40 sgp;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

bool initSensors() {
  Wire.begin();

  if (!sht4.begin()) {
    Serial.println("ERROR: SHT41 not found (0x44)");
    return false;
  }
  if (!sgp.begin()) {
    Serial.println("ERROR: SGP40 not found (0x59)");
    return false;
  }

  sht4.setPrecision(SHT4X_HIGH_PRECISION);
  sht4.setHeater(SHT4X_NO_HEATER);

  Serial.println("OK: SHT41 + SGP40 ready");
  return true;
}

bool readSensors(float* air_temp_c, float* air_rh_pct, uint16_t* air_voc_raw) {
  sensors_event_t humidity_evt, temp_evt;
  sht4.getEvent(&humidity_evt, &temp_evt);
  uint16_t voc_raw = sgp.measureRaw();

  if (isnan(temp_evt.temperature) || isnan(humidity_evt.relative_humidity)) {
    return false;
  }

  *air_temp_c = temp_evt.temperature;
  *air_rh_pct = humidity_evt.relative_humidity;
  *air_voc_raw = voc_raw;
  return true;
}

void postSensorJson(float air_temp_c, float air_rh_pct, uint16_t air_voc_raw) {
  char json[160];
  snprintf(
      json,
      sizeof(json),
      "{\"air_temp_c\":%.2f,\"air_rh_pct\":%.2f,\"air_voc_raw\":%u}",
      air_temp_c,
      air_rh_pct,
      static_cast<unsigned int>(air_voc_raw));

  HTTPClient http;
  String url = "http://" + String(API_HOST) + ":" + String(API_PORT) + String(API_PATH);
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  int code = http.POST((uint8_t*)json, strlen(json));
  Serial.printf("POST %s -> %d | %s\n", API_PATH, code, json);
  if (code > 0) {
    Serial.println(http.getString());
  } else {
    Serial.printf("HTTP error: %s\n", http.errorToString(code).c_str());
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(300);

  connectWiFi();

  if (!initSensors()) {
    while (true) {
      delay(1000);
    }
  }
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  uint32_t now = millis();
  if (now - last_send_ms >= SEND_EVERY_MS) {
    last_send_ms = now;

    float air_temp_c = 0.0f;
    float air_rh_pct = 0.0f;
    uint16_t air_voc_raw = 0;

    if (!readSensors(&air_temp_c, &air_rh_pct, &air_voc_raw)) {
      Serial.println("Sensor read failed");
      return;
    }

    postSensorJson(air_temp_c, air_rh_pct, air_voc_raw);
  }
}

