/*
 * ELEGOO Smart Robot Car V4.0 -- UNO R3 Car V2.0
 * v5: drive, BME280/BMP280 auto-detect, HC-SR04 ultrasonic, corrected camera pan direction.
 * Serial link to original ELEGOO ESP32-S3 camera at 9600 baud.
 *
 * ESP32 -> UNO, newline-delimited:
 *   D,<signed-left-PWM>,<signed-right-PWM>   (-255..255)
 *   S                                      stop motors
 *   P,<degrees>                            camera pan 45..135 degrees
 *
 * UNO -> ESP32, newline-delimited:
 *   T,<degC>,<humidity-percent>,<pressure-hPa>  genuine BME280
 *   B,<degC>,<pressure-hPa>                    BMP280 (no humidity hardware)
 *   E,ENV                                       environmental sensor missing/error
 *   U,<distance-cm>                             ultrasonic reading, 1 decimal
 *   U,-1                                        no reliable ultrasonic echo
 *   P,<degrees>                                 last commanded pan angle
 *
 * ELEGOO official V4 pin map:
 *   Motor standby D3; right PWM D5, left PWM D6; right dir D7, left dir D8
 *   Ultrasonic: TRIG D13, ECHO D12
 *   Servo Z axis (pan): D10; second/Y servo (tilt): D11, unused here
 *   Environmental I2C: SDA A4/SDA, SCL A5/SCL
 *
 * Your tested purple "280" board reports chip ID 0x58 at address 0x76,
 * which identifies it as BMP280. It can report temperature + pressure,
 * but cannot measure humidity. This sketch also supports a future BME280
 * (chip ID 0x60) automatically.
 *
 * WARNING: ultrasonic distance around 2 cm is at the sensor's minimum range.
 * Dashboard warning is ADVISORY ONLY, not automatic collision prevention.
 */
#include <Arduino.h>
#include <Wire.h>
#include <Servo.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <Adafruit_BMP280.h>
#include <math.h>

static const uint8_t RIGHT_PWM = 5;
static const uint8_t LEFT_PWM = 6;
static const uint8_t RIGHT_DIR = 7;
static const uint8_t LEFT_DIR = 8;
static const uint8_t MOTOR_STBY = 3;
static const uint8_t TRIG_PIN = 13;
static const uint8_t ECHO_PIN = 12;
static const uint8_t CAMERA_PAN_PIN = 10;

// Conservative camera travel until physical clearances are verified.
static const int PAN_MIN_DEG = 45;
static const int PAN_MAX_DEG = 135;
static const int PAN_CENTER_DEG = 90;
// Physical D10 servo is mounted in the opposite direction from the UI convention.
// Keep UI/serial semantics intuitive: 45 = LEFT, 90 = CENTER, 135 = RIGHT.
static const bool PAN_SERVO_REVERSED = true;
static const unsigned long PAN_HOLD_MS = 650;
static const unsigned long MOTOR_TIMEOUT_MS = 450;
static const unsigned long ENV_PERIOD_MS = 1000;
static const unsigned long SONAR_PERIOD_MS = 250;
static const unsigned long PAN_REPORT_MS = 2000;

Adafruit_BME280 bme;
Adafruit_BMP280 bmp;
Servo panServo;

enum EnvSensorType : uint8_t {
  ENV_NONE = 0,
  ENV_BME280,
  ENV_BMP280
};

EnvSensorType envSensor = ENV_NONE;
bool motorsMoving = false;
int cameraPanDeg = PAN_CENTER_DEG;
unsigned long lastDriveMs = 0;
unsigned long lastEnvMs = 0;
unsigned long lastSonarMs = 0;
unsigned long lastPanReportMs = 0;
unsigned long panMoveMs = 0;
char lineBuf[40];
uint8_t lineLen = 0;
bool discardUntilNewline = false;

void setDrive(int left, int right) {
  left = constrain(left, -255, 255);
  right = constrain(right, -255, 255);
  digitalWrite(LEFT_DIR, left >= 0 ? HIGH : LOW);
  digitalWrite(RIGHT_DIR, right >= 0 ? HIGH : LOW);
  analogWrite(LEFT_PWM, abs(left));
  analogWrite(RIGHT_PWM, abs(right));
  motorsMoving = (left != 0 || right != 0);
  digitalWrite(MOTOR_STBY, motorsMoving ? HIGH : LOW);
}

void moveCamera(int deg) {
  // cameraPanDeg is the semantic angle used by the web UI:
  // 45 = LEFT, 90 = CENTER, 135 = RIGHT.
  cameraPanDeg = constrain(deg, PAN_MIN_DEG, PAN_MAX_DEG);

  // Your physical servo is installed in the reverse direction, so translate the
  // semantic angle before writing to D10. Center (90°) remains unchanged.
  const int servoDeg = PAN_SERVO_REVERSED ? (180 - cameraPanDeg) : cameraPanDeg;

  if (!panServo.attached()) panServo.attach(CAMERA_PAN_PIN);
  panServo.write(constrain(servoDeg, 0, 180));
  panMoveMs = millis();

  // Report the semantic/UI angle, not the raw physical servo angle.
  Serial.print(F("P,"));
  Serial.println(cameraPanDeg);
}

void processLine(char *line) {
  if (!strcmp(line, "S")) {
    setDrive(0, 0);
    lastDriveMs = millis();
    return;
  }

  int left = 0, right = 0, angle = 0;
  char extra;

  if (sscanf(line, "D,%d,%d%c", &left, &right, &extra) == 2 &&
      left >= -255 && left <= 255 && right >= -255 && right <= 255) {
    setDrive(left, right);
    lastDriveMs = millis();
    return;
  }

  if (sscanf(line, "P,%d%c", &angle, &extra) == 1 &&
      angle >= PAN_MIN_DEG && angle <= PAN_MAX_DEG) {
    moveCamera(angle);
  }
}

void readIncoming() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (!discardUntilNewline && lineLen) {
        lineBuf[lineLen] = '\0';
        processLine(lineBuf);
      }
      lineLen = 0;
      discardUntilNewline = false;
    } else if (!discardUntilNewline) {
      if (lineLen < sizeof(lineBuf) - 1) {
        lineBuf[lineLen++] = c;
      } else {
        lineLen = 0;
        discardUntilNewline = true;
      }
    }
  }
}

void detectEnvironmentalSensor() {
  envSensor = ENV_NONE;

  // A real BME280 returns chip ID 0x60. Try both common I2C addresses.
  if (bme.begin(0x76) || bme.begin(0x77)) {
    envSensor = ENV_BME280;
    return;
  }

  // BMP280 returns chip ID 0x58. It has temperature + pressure, no humidity.
  if (bmp.begin(0x76) || bmp.begin(0x77)) {
    envSensor = ENV_BMP280;
    bmp.setSampling(
      Adafruit_BMP280::MODE_NORMAL,
      Adafruit_BMP280::SAMPLING_X2,   // temperature
      Adafruit_BMP280::SAMPLING_X16,  // pressure
      Adafruit_BMP280::FILTER_X16,
      Adafruit_BMP280::STANDBY_MS_500
    );
  }
}

void reportEnvironment() {
  if (envSensor == ENV_BME280) {
    const float t = bme.readTemperature();
    const float h = bme.readHumidity();
    const float p = bme.readPressure() / 100.0F;

    if (!isfinite(t) || !isfinite(h) || !isfinite(p)) {
      Serial.println(F("E,ENV"));
      return;
    }

    Serial.print(F("T,"));
    Serial.print(t, 2);
    Serial.print(',');
    Serial.print(h, 2);
    Serial.print(',');
    Serial.println(p, 2);
    return;
  }

  if (envSensor == ENV_BMP280) {
    const float t = bmp.readTemperature();
    const float p = bmp.readPressure() / 100.0F;

    if (!isfinite(t) || !isfinite(p)) {
      Serial.println(F("E,ENV"));
      return;
    }

    Serial.print(F("B,"));
    Serial.print(t, 2);
    Serial.print(',');
    Serial.println(p, 2);
    return;
  }

  Serial.println(F("E,ENV"));
}

void reportSonar() {
  // 10 us trigger. pulseIn timeout is ~18 ms (~300 cm). No echo = unknown.
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long durationUs = pulseIn(ECHO_PIN, HIGH, 18000UL);
  if (durationUs == 0) {
    Serial.println(F("U,-1")); // Never treat timeout as a clear path.
    return;
  }

  const float cm = durationUs / 58.0F;
  if (cm > 300.0F) {
    Serial.println(F("U,-1"));
  } else {
    Serial.print(F("U,"));
    Serial.println(cm, 1);
  }
}

void setup() {
  pinMode(RIGHT_PWM, OUTPUT);
  pinMode(LEFT_PWM, OUTPUT);
  pinMode(RIGHT_DIR, OUTPUT);
  pinMode(LEFT_DIR, OUTPUT);
  pinMode(MOTOR_STBY, OUTPUT);
  setDrive(0, 0);

  pinMode(TRIG_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);
  pinMode(ECHO_PIN, INPUT);

  Serial.begin(9600);
  Wire.begin();
  detectEnvironmentalSensor();

  // Center camera at boot, then detach after it has time to move.
  moveCamera(PAN_CENTER_DEG);

  lastDriveMs = millis();
  lastEnvMs = millis();
  lastSonarMs = millis();
  lastPanReportMs = millis();
}

void loop() {
  readIncoming();
  const unsigned long now = millis();

  if (motorsMoving && now - lastDriveMs > MOTOR_TIMEOUT_MS) {
    setDrive(0, 0);
  }

  if (panServo.attached() && now - panMoveMs >= PAN_HOLD_MS) {
    panServo.detach();
  }

  if (now - lastSonarMs >= SONAR_PERIOD_MS) {
    lastSonarMs = now;
    reportSonar();
  }

  if (now - lastEnvMs >= ENV_PERIOD_MS) {
    lastEnvMs = now;
    reportEnvironment();
  }

  if (now - lastPanReportMs >= PAN_REPORT_MS) {
    lastPanReportMs = now;
    Serial.print(F("P,"));
    Serial.println(cameraPanDeg);
  }
}
