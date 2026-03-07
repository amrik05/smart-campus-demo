#include <WiFi.h>
#include <HTTPClient.h>
#include <OneWire.h>
#include <DallasTemperature.h>

// ===== Pins =====
#define ONE_WIRE_PIN 4
#define TURB_PIN 5
#define TDS_PIN 6

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature ds18b20(&oneWire);

// ===== WiFi + API config =====
const char* WIFI_SSID = "";
const char* WIFI_PASS = "";
const char* API_HOST = "";
const int   API_PORT = 8001;
const char* API_PATH = "/telemetry/water/raw";

static const uint32_t SEND_EVERY_MS = 1000;
uint32_t last_send_ms = 0;

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
  ds18b20.begin();
  analogReadResolution(12);

  Serial.println("OK: DS18B20 + Analog sensors ready");
  return true;
}

bool readSensors(float* surface_temp_c,
                 int* turb_raw,
                 int* tds_raw,
                 float* turb_v,
                 float* tds_v) {

  ds18b20.requestTemperatures();
  float temp = ds18b20.getTempCByIndex(0);

  if (temp == DEVICE_DISCONNECTED_C) {
    return false;
  }

  int turbidity = analogRead(TURB_PIN);
  int tds = analogRead(TDS_PIN);

  float turb_voltage = turbidity * (3.3f / 4095.0f);
  float tds_voltage  = tds * (3.3f / 4095.0f);

  *surface_temp_c = temp;
  *turb_raw = turbidity;
  *tds_raw = tds;
  *turb_v = turb_voltage;
  *tds_v = tds_voltage;

  return true;
}

void postSensorJson(float surface_temp_c,
                    int turb_raw,
                    int tds_raw,
                    float turb_v,
                    float tds_v) {

  char json[240];

  snprintf(
    json,
    sizeof(json),
    "{\"surface_temp_c\":%.2f,"
    "\"turbidity_raw\":%d,"
    "\"tds_raw\":%d,"
    "\"turbidity_v\":%.4f,"
    "\"tds_v\":%.4f}",
    surface_temp_c,
    turb_raw,
    tds_raw,
    turb_v,
    tds_v
  );

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

    float surface_temp_c = 0.0f;
    int turb_raw = 0;
    int tds_raw = 0;
    float turb_v = 0.0f;
    float tds_v = 0.0f;

    if (!readSensors(&surface_temp_c, &turb_raw, &tds_raw, &turb_v, &tds_v)) {
      Serial.println("Sensor read failed");
      return;
    }

    postSensorJson(surface_temp_c, turb_raw, tds_raw, turb_v, tds_v);
  }
}