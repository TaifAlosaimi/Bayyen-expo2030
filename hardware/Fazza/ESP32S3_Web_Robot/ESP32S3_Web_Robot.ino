/*
 * ESP32S3-Camera-V1.3 + OV3660 - video, drive, BME280/BMP280, pan, ultrasonic.
 * Arduino IDE board: ESP32S3 Dev Module (esp32 by Espressif Systems 3.x).
 * Flash: 8 MB (if module label is N8R8); PSRAM: OPI; USB CDC on boot: enabled.
 *
 * Access point: ELEGOO-Web-Car / change password below
 * Dashboard:     http://192.168.4.1/
 * MJPEG camera:  http://192.168.4.1:81/stream
 * WebSocket:     ws://192.168.4.1:82/
 * Car UART (original 4-wire plug): RX GPIO3, TX GPIO40 @ 9600 baud.
 * No external ESP32->UNO UART wiring required if original shield/cable fitted.
 */
#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <WebSocketsServer.h> // Install library "WebSockets" by Markus Sattler (Links2004)
#include <esp_camera.h>
#include <esp_http_server.h>
#include "camera_pins.h"
#include "dashboard.h"

static const char *AP_NAME = "ELEGOO-Web-Car";
static const char *AP_PASSWORD = "ChangeMe2026"; // CHANGE BEFORE FIRST USE (8+ chars)
static const int UNO_RX = 3;
static const int UNO_TX = 40;
static const uint32_t UNO_BAUD = 9600;
static const unsigned long COMMAND_TIMEOUT_MS = 350;

WebServer web(80);
WebSocketsServer ws(82);
httpd_handle_t streamServer = nullptr;
String serialLine;
unsigned long lastValidDriveMs = 0;
bool driveActive = false;
int lastPanAngle = 90; // last reported UNO position
bool panSeen = false; // do not claim UNO position before actual telemetry

void stopRobot() {
  Serial2.print("S\n");
  driveActive = false;
  lastValidDriveMs = millis();
}

void sendDrive(int left, int right) {
  left = constrain(left, -255, 255);
  right = constrain(right, -255, 255);
  Serial2.printf("D,%d,%d\n", left, right);
  driveActive = left != 0 || right != 0;
  lastValidDriveMs = millis();
}

void wsEvent(uint8_t client, WStype_t type, uint8_t *payload, size_t length) {
  if (type == WStype_DISCONNECTED) {
    stopRobot(); // Safe default, even when there are multiple browser tabs.
    return;
  }
  if (type == WStype_CONNECTED) {
    stopRobot();
    ws.sendTXT(client, "{\"type\":\"ready\"}");
    if (panSeen) {
      char panState[50];
      snprintf(panState, sizeof(panState), "{\"type\":\"pan\",\"angle\":%d}", lastPanAngle);
      ws.sendTXT(client, panState);
    }
    return;
  }
  if (type != WStype_TEXT || length > 64) return;
  String message;
  message.reserve(length + 1);
  for (size_t i = 0; i < length; ++i) message += (char)payload[i];
  if (message == "S") {
    stopRobot();
    return;
  }
  int left, right;
  char extra;
  if (sscanf(message.c_str(), "D,%d,%d%c", &left, &right, &extra) == 2 &&
      left >= -255 && left <= 255 && right >= -255 && right <= 255) {
    sendDrive(left, right);
    return;
  }
  int angle = 0;
  if (sscanf(message.c_str(), "P,%d%c", &angle, &extra) == 1 &&
      angle >= 45 && angle <= 135) {
    Serial2.printf("P,%d\n", angle);
  }
}

void handleUnoLine(const String &line) {
  float t, h, p;

  // Genuine BME280: temperature + humidity + pressure.
  if (sscanf(line.c_str(), "T,%f,%f,%f", &t, &h, &p) == 3 &&
      isfinite(t) && isfinite(h) && isfinite(p)) {
    char json[190];
    snprintf(json, sizeof(json),
             "{\"type\":\"sensor\",\"available\":true,\"sensor\":\"BME280\","
             "\"humidityAvailable\":true,\"temperature\":%.2f,\"humidity\":%.2f,\"pressure\":%.2f}",
             t, h, p);
    ws.broadcastTXT(json);

  // BMP280: temperature + pressure only. There is no humidity sensor in this chip.
  } else if (sscanf(line.c_str(), "B,%f,%f", &t, &p) == 2 &&
             isfinite(t) && isfinite(p)) {
    char json[180];
    snprintf(json, sizeof(json),
             "{\"type\":\"sensor\",\"available\":true,\"sensor\":\"BMP280\","
             "\"humidityAvailable\":false,\"temperature\":%.2f,\"pressure\":%.2f}",
             t, p);
    ws.broadcastTXT(json);

  } else if (line == "E,ENV" || line == "E,BME") {
    ws.broadcastTXT("{\"type\":\"sensor\",\"available\":false}");

  } else if (line.startsWith("U,")) {
    float cm = -3.0f;
    char extra;
    if (sscanf(line.c_str(), "U,%f%c", &cm, &extra) == 1 && isfinite(cm)) {
      if (cm < 0 || cm > 300) {
        ws.broadcastTXT("{\"type\":\"ultrasonic\",\"valid\":false}");
      } else {
        char json[100];
        snprintf(json, sizeof(json),
                 "{\"type\":\"ultrasonic\",\"valid\":true,\"distance\":%.1f}", cm);
        ws.broadcastTXT(json);
      }
    }
  } else if (line.startsWith("P,")) {
    int angle = 0;
    char extra;
    if (sscanf(line.c_str(), "P,%d%c", &angle, &extra) == 1 &&
        angle >= 45 && angle <= 135) {
      lastPanAngle = angle;
      panSeen = true;
      char json[60];
      snprintf(json, sizeof(json), "{\"type\":\"pan\",\"angle\":%d}", angle);
      ws.broadcastTXT(json);
    }
  }
}

void pumpUnoSerial() {
  while (Serial2.available()) {
    const char c = (char)Serial2.read();
    if (c == '\n' || c == '\r') {
      if (serialLine.length()) {
        handleUnoLine(serialLine);
        serialLine = "";
      }
    } else if (serialLine.length() < 96) {
      serialLine += c;
    } else {
      serialLine = "";
    }
  }
}

static esp_err_t streamHandler(httpd_req_t *req) {
  static const char *contentType = "multipart/x-mixed-replace;boundary=elecarframe";
  static const char *boundary = "\r\n--elecarframe\r\n";
  static const char *partHeader = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";
  httpd_resp_set_type(req, contentType);
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  esp_err_t result = ESP_OK;
  while (true) {
    camera_fb_t *frame = esp_camera_fb_get();
    if (!frame) { result = ESP_FAIL; break; }
    if (frame->format != PIXFORMAT_JPEG) {
      esp_camera_fb_return(frame);
      result = ESP_FAIL;
      break;
    }
    char header[70];
    const int headerLen = snprintf(header, sizeof(header), partHeader, (unsigned)frame->len);
    result = httpd_resp_send_chunk(req, boundary, strlen(boundary));
    if (result == ESP_OK) result = httpd_resp_send_chunk(req, header, headerLen);
    if (result == ESP_OK) result = httpd_resp_send_chunk(req, (const char*)frame->buf, frame->len);
    esp_camera_fb_return(frame);
    if (result != ESP_OK) break; // Browser disconnected.
    vTaskDelay(pdMS_TO_TICKS(35)); // Give time to network / other camera tasks.
  }
  return result;
}

bool startCamera() {
  camera_config_t c = {};
  c.ledc_channel = LEDC_CHANNEL_0;
  c.ledc_timer = LEDC_TIMER_0;
  c.pin_d0 = Y2_GPIO_NUM;
  c.pin_d1 = Y3_GPIO_NUM;
  c.pin_d2 = Y4_GPIO_NUM;
  c.pin_d3 = Y5_GPIO_NUM;
  c.pin_d4 = Y6_GPIO_NUM;
  c.pin_d5 = Y7_GPIO_NUM;
  c.pin_d6 = Y8_GPIO_NUM;
  c.pin_d7 = Y9_GPIO_NUM;
  c.pin_xclk = XCLK_GPIO_NUM;
  c.pin_pclk = PCLK_GPIO_NUM;
  c.pin_vsync = VSYNC_GPIO_NUM;
  c.pin_href = HREF_GPIO_NUM;
  c.pin_sccb_sda = SIOD_GPIO_NUM;
  c.pin_sccb_scl = SIOC_GPIO_NUM;
  c.pin_pwdn = PWDN_GPIO_NUM;
  c.pin_reset = RESET_GPIO_NUM;
  c.xclk_freq_hz = 20000000;
  c.pixel_format = PIXFORMAT_JPEG;
  c.frame_size = FRAMESIZE_VGA; // 640 x 480
  c.jpeg_quality = 14;
  c.fb_count = psramFound() ? 2 : 1;
  c.fb_location = psramFound() ? CAMERA_FB_IN_PSRAM : CAMERA_FB_IN_DRAM;
  c.grab_mode = psramFound() ? CAMERA_GRAB_LATEST : CAMERA_GRAB_WHEN_EMPTY;
  esp_err_t status = esp_camera_init(&c);
  if (status != ESP_OK) {
    Serial.printf("Camera init FAILED: 0x%x\n", status);
    return false;
  }
  // Your camera is physically mounted upside down. A 180-degree image
  // correction requires vertical flip + horizontal mirror.
  sensor_t *sensor = esp_camera_sensor_get();
  if (sensor) {
    sensor->set_vflip(sensor, 1);
    sensor->set_hmirror(sensor, 1);
  }
  return true;
}

bool startStreamServer() {
  httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();
  cfg.server_port = 81;
  cfg.ctrl_port = 32769;
  cfg.stack_size = 8192;
  if (httpd_start(&streamServer, &cfg) != ESP_OK) return false;
  httpd_uri_t stream = {};
  stream.uri = "/stream";
  stream.method = HTTP_GET;
  stream.handler = streamHandler;
  return httpd_register_uri_handler(streamServer, &stream) == ESP_OK;
}

void setup() {
  Serial.begin(115200); // USB debug serial; not used for UNO commands.
  delay(250);
  Serial2.begin(UNO_BAUD, SERIAL_8N1, UNO_RX, UNO_TX);
  stopRobot();

  bool cameraOK = startCamera();
  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  if (!WiFi.softAP(AP_NAME, AP_PASSWORD)) {
    Serial.println("Wi-Fi access point FAILED");
  } else {
    Serial.print("Dashboard URL: http://");
    Serial.println(WiFi.softAPIP());
  }

  web.on("/", HTTP_GET, []() {
    web.send_P(200, "text/html; charset=utf-8", DASHBOARD_HTML);
  });
  web.on("/status", HTTP_GET, [cameraOK]() {
    web.send(200, "application/json", cameraOK ? "{\"camera\":true}" : "{\"camera\":false}");
  });
  web.begin();
  ws.begin();
  ws.onEvent(wsEvent);
  if (cameraOK && !startStreamServer()) Serial.println("Stream server failed");
  Serial.println("Setup complete");
}

void loop() {
  web.handleClient();
  ws.loop();
  pumpUnoSerial();
  if (driveActive && millis() - lastValidDriveMs > COMMAND_TIMEOUT_MS) {
    stopRobot();
  }
  delay(1);
}
