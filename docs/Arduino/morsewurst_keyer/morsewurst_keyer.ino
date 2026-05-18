// ======================================================
// MORSEWURST USB / BOARD CONFIGURATION NOTE
// ======================================================
//
// This firmware is built for an ESP32-S3 board with native USB support,
// originally the Adafruit ESP32-S3 Feather with STEMMA QT, 8MB Flash, no PSRAM.
//
// The firmware uses USB in two different ways at the same time:
//
//   1. USB CDC Serial
//      Used for raw timing telemetry read by the Python Morsewurst
//      training software.
//
//   2. USB HID Keyboard
//      Used for sending decoded Morse characters to the computer as
//      keyboard input.
//
// For Arduino IDE / ESP32 board settings, the important options are:
//
//   USB Mode:        USB-OTG (TinyUSB)
//   USB CDC On Boot: Enabled
//   Upload Mode:     USB-OTG CDC (TinyUSB)
//
// If USB CDC On Boot is disabled, the Python program may not see the
// telemetry serial port correctly. If TinyUSB / USB-OTG mode is not used,
// USB HID keyboard support may not work as expected.
//
// Other ESP32-S3 boards may work if they have native USB support and the
// pins are adjusted to match the hardware. Boards without native USB may
// still provide serial telemetry through a USB-to-UART adapter, but USB HID
// keyboard mode will not work in the same way.
//
// Use a USB data cable, not a charge-only cable.
// ======================================================

#include <Arduino.h>
#include <Wire.h>
#include <U8g2lib.h>
#include <Preferences.h>
#include "USB.h"
#include "USBHIDKeyboard.h"
#include <inttypes.h>
#include "esp_timer.h"

// ======================================================
// USB HID KEYBOARD
// ======================================================
USBHIDKeyboard Keyboard;
Preferences prefs;

// ======================================================
// OLED 128x64 SSD1306 I2C, U8g2
// ======================================================
U8G2_SH1106_128X64_NONAME_F_HW_I2C u8g2(
  U8G2_R2,
  U8X8_PIN_NONE
);

// ======================================================
// PINIT
// ======================================================
const int AUDIO_PIN = 11;

const int STRAIGHT_KEY_PIN = 12;
const int DIT_PIN = 9;
const int DAH_PIN = 10;

const int ENC_CLK_PIN = 5;
const int ENC_DT_PIN = 6;
const int ENC_SW_PIN = 13;

const int HEADPHONE_DETECT_PIN = A3;

#ifndef TFT_I2C_POWER
#define TFT_I2C_POWER -1
#endif

// ======================================================
// USB JA DEBUG
// ======================================================
const unsigned long USB_START_DELAY_MS = 1500;

// ======================================================
// SETTINGS
// ======================================================
struct Settings {
  int wpm = 20;
  int toneHz = 600;
  int letterGapTenths = 30;
  int wordGapTenths = 70;

  bool usbKeyboard = true;
  bool serialOutput = false;
  bool serialTelemetry = true;

  bool iambicEnabled = true;
  bool straightEnabled = true;

  bool sidetoneEnabled = true;
  bool headphonesOnly = false;

  bool autoSpace = true;
  bool swapPaddles = false;

  int iambicMode = 1;
  int displayTimeoutIndex = 4;
};

Settings settings;

const unsigned long DISPLAY_TIMEOUT_VALUES[] = {
  5000UL,
  30000UL,
  60000UL,
  5UL * 60UL * 1000UL,
  10UL * 60UL * 1000UL,
  15UL * 60UL * 1000UL,
  30UL * 60UL * 1000UL,
  60UL * 60UL * 1000UL,
  6UL * 60UL * 60UL * 1000UL,
  12UL * 60UL * 60UL * 1000UL,
  24UL * 60UL * 60UL * 1000UL
};

const char* DISPLAY_TIMEOUT_LABELS[] = {
  "5 sec",
  "30 sec",
  "1 min",
  "5 min",
  "10 min",
  "15 min",
  "30 min",
  "1 h",
  "6 h",
  "12 h",
  "24 h"
};

const int DISPLAY_TIMEOUT_COUNT =
  sizeof(DISPLAY_TIMEOUT_VALUES) / sizeof(DISPLAY_TIMEOUT_VALUES[0]);

// ======================================================
// MENU TYPES
// ======================================================
enum ScreenMode {
  SCREEN_HOME,
  SCREEN_MENU,
  SCREEN_EDIT_BOOL,
  SCREEN_EDIT_INT,
  SCREEN_EDIT_LIST,
  SCREEN_ABOUT
};

enum MenuItemType {
  MENU_ACTION_BACK,
  MENU_BOOL,
  MENU_INT,
  MENU_LIST,
  MENU_ACTION_ABOUT,
  MENU_ACTION_SAVE,
  MENU_ACTION_RESET
};

enum SettingId {
  SET_USB_KEYBOARD,
  SET_SERIAL_OUTPUT,
  SET_SERIAL_TELEMETRY,
  SET_IAMBIC,
  SET_STRAIGHT,
  SET_SIDETONE,
  SET_HEADPHONES_ONLY,
  SET_AUTOSPACE,
  SET_SWAP_PADDLES,
  SET_WPM,
  SET_TONE,
  SET_IAMBIC_MODE,
  SET_DISPLAY_TIMEOUT,
  SET_LETTER_GAP,
  SET_WORD_GAP
};

struct MenuItem {
  const char* label;
  MenuItemType type;
  int settingId;
  int minVal;
  int maxVal;
  int step;
};

// ======================================================
// FUNCTION DECLARATIONS
// ======================================================
bool headphonesConnected();
bool allowSidetone();

void audioConfigure();
void audioStart();
void audioStop();

uint64_t iambicUnit();

void updateEncoder();
int getEncoderSteps();
void updateButton();
bool consumeButtonPress();

void outputChar(char c);
void addToPreview(char c);

void telemetryHello();
void telemetryToneRaw(const char* source, uint64_t t0, uint64_t t1, uint64_t duration);
void telemetryToneElement(const char* source, char element, uint64_t t0, uint64_t t1, uint64_t duration);
float estimatedWpm();
void jsonPrintString(const String& value);
void jsonPrintChar(char c);

char decodeMorse(String code);
void finishLetter();
void checkLetterAndWordSpace();
void updateDitEstimate(uint64_t pressDuration);
void addStraightElement(uint64_t pressStart, uint64_t pressDuration);
void addIambicElement(char element, uint64_t elementStart, uint64_t elementEnd);

void handleStraightKey(bool straightPressed);

bool ditPressedNow();
bool dahPressedNow();
bool keyerBusy();
void sampleOppositePaddleDuringElement(char currentElement);
void toneWithIambicSampling(uint64_t duration, char currentElement);
void silenceWithIambicSampling(uint64_t duration, char currentElement);
void sendIambicElement(char element);
char chooseCurrentPressedElement();
void handleIambic();
void handleQueuedIambicChange();

void wakeDisplay();
unsigned long displaySleepMs();
void checkDisplaySleep();
String displayTimeoutText();

void saveSettings();
void loadSettings();
void resetDefaults();

bool getBoolSetting(int id);
void setBoolSetting(int id, bool value);
int getIntSetting(int id);
void setIntSetting(int id, int value);

String boolText(bool value);
String tenthsText(int value);
String iambicModeText();
String listValueText(int id);
String menuValueText(const MenuItem& item);
String currentModeText();

void drawHeader(const char* title);
void drawHome();
void drawMenu();
void drawEdit();
void drawAbout();
void enterAbout();
void exitAbout();
void handleAboutInput(int steps, bool pressed);
void buildAboutLines();
void addAboutLine(String line);
void drawMessage(const char* line1, const char* line2);
void requestDisplayUpdate();
void requestSafeDisplayUpdate();
void updateDisplay();

void enterMenu();
void exitMenu();
void handleHomeInput(int steps, bool pressed);
void handleMenuInput(int steps, bool pressed);
void handleEditInput(int steps, bool pressed);
void handleUi();

void telemetryHeartbeat();

// ======================================================
// AUDIO, SQUARE ONLY
// ======================================================
const int AUDIO_RESOLUTION = 8;
const int AUDIO_BASE_PWM = 62500;

bool audioActive = false;

bool headphonesConnected() {
  return digitalRead(HEADPHONE_DETECT_PIN) == LOW;
}

bool allowSidetone() {
  if (!settings.sidetoneEnabled) return false;
  if (settings.headphonesOnly && !headphonesConnected()) return false;
  return true;
}

void audioConfigure() {
  pinMode(AUDIO_PIN, OUTPUT);
  ledcAttach(AUDIO_PIN, AUDIO_BASE_PWM, AUDIO_RESOLUTION);
  ledcWriteTone(AUDIO_PIN, 0);
  ledcWrite(AUDIO_PIN, 0);
}

void audioStart() {
  if (!allowSidetone()) return;
  if (audioActive) return;

  audioActive = true;
  ledcWriteTone(AUDIO_PIN, settings.toneHz);
}

void audioStop() {
  if (!audioActive) return;

  audioActive = false;
  ledcWriteTone(AUDIO_PIN, 0);
  ledcWrite(AUDIO_PIN, 0);
}

// ======================================================
// MORSE STATE
// ======================================================
bool nextIambicDit = true;
bool queuedDit = false;
bool queuedDah = false;

String currentSymbol = "";
String outputPreview = "";

bool lastStraightState = false;

uint64_t straightDownStart = 0;
uint64_t lastElementEnd = 0;

double estimatedDit = 100000.0;

const uint64_t MIN_PRESS = 10000ULL;
const uint64_t MAX_REASONABLE_DIT = 300000ULL;

const String EASTER_EGG_CODE = ".................";
const char* EASTER_EGG_TEXT = "WOLOLO";

bool wordSpacePrinted = false;

uint64_t iambicUnit() {
  return 1200000ULL / (uint64_t)settings.wpm;
}

// ======================================================
// ROTARY ENCODER
// ======================================================
int lastEncState = 0;
int encoderDelta = 0;

bool lastButtonReading = HIGH;
bool buttonState = HIGH;
unsigned long lastButtonChange = 0;

const unsigned long BUTTON_DEBOUNCE_MS = 35;

bool buttonPressedEvent = false;

void updateEncoder() {
  int msb = digitalRead(ENC_CLK_PIN);
  int lsb = digitalRead(ENC_DT_PIN);

  int encoded = (msb << 1) | lsb;
  int sum = (lastEncState << 2) | encoded;

  if (
    sum == 0b1101 ||
    sum == 0b0100 ||
    sum == 0b0010 ||
    sum == 0b1011
  ) {
    encoderDelta++;
  }

  if (
    sum == 0b1110 ||
    sum == 0b0111 ||
    sum == 0b0001 ||
    sum == 0b1000
  ) {
    encoderDelta--;
  }

  lastEncState = encoded;
}

int getEncoderSteps() {
  if (encoderDelta >= 4) {
    encoderDelta = 0;
    return 1;
  }

  if (encoderDelta <= -4) {
    encoderDelta = 0;
    return -1;
  }

  return 0;
}

void updateButton() {
  bool reading = digitalRead(ENC_SW_PIN);

  if (reading != lastButtonReading) {
    lastButtonChange = millis();
  }

  if ((millis() - lastButtonChange) > BUTTON_DEBOUNCE_MS) {
    if (reading != buttonState) {
      buttonState = reading;

      if (buttonState == LOW) {
        buttonPressedEvent = true;
      }
    }
  }

  lastButtonReading = reading;
}

bool consumeButtonPress() {
  if (!buttonPressedEvent) return false;

  buttonPressedEvent = false;
  return true;
}

// ======================================================
// MORSE TABLE
// ======================================================
struct MorseMap {
  const char* code;
  char letter;
};

MorseMap morseTable[] = {
  {".-", 'A'}, {"-...", 'B'}, {"-.-.", 'C'}, {"-..", 'D'},
  {".", 'E'}, {"..-.", 'F'}, {"--.", 'G'}, {"....", 'H'},
  {"..", 'I'}, {".---", 'J'}, {"-.-", 'K'}, {".-..", 'L'},
  {"--", 'M'}, {"-.", 'N'}, {"---", 'O'}, {".--.", 'P'},
  {"--.-", 'Q'}, {".-.", 'R'}, {"...", 'S'}, {"-", 'T'},
  {"..-", 'U'}, {"...-", 'V'}, {".--", 'W'}, {"-..-", 'X'},
  {"-.--", 'Y'}, {"--..", 'Z'},

  {"-----", '0'}, {".----", '1'}, {"..---", '2'}, {"...--", '3'},
  {"....-", '4'}, {".....", '5'}, {"-....", '6'}, {"--...", '7'},
  {"---..", '8'}, {"----.", '9'},

  {".-.-.-", '.'},
  {"--..--", ','},
  {"..--..", '?'},
  {"-.-.--", '!'},
  {"-..-.", '/'},
  {"-.--.", '('},
  {"-.--.-", ')'},
  {".-...", '&'},
  {"---...", ':'},
  {"-.-.-.", ';'},
  {"-...-", '='},
  {".-.-.", '+'},
  {"-....-", '-'},
  {"..--.-", '_'},
  {".-..-.", '"'},
  {".--.-.", '@'},
  {"...-..-", '$'},
  {".----.", '\''}
};

const int morseTableSize = sizeof(morseTable) / sizeof(morseTable[0]);

// ======================================================
// OUTPUT
// ======================================================
uint64_t nowTime() {
  return (uint64_t)esp_timer_get_time();
}

void serialPrintUint64(uint64_t value) {
  Serial.printf("%" PRIu64, value);
}

float estimatedWpm() {
  if (estimatedDit <= 0.0) return 0.0;
  return 1200000.0 / estimatedDit;
}

void jsonPrintString(const String& value) {
  Serial.print("\"");

  for (unsigned int i = 0; i < value.length(); i++) {
    char c = value[i];

    if (c == '\\') {
      Serial.print("\\\\");
    } else if (c == '"') {
      Serial.print("\\\"");
    } else if (c == '\b') {
      Serial.print("\\b");
    } else if (c == '\n') {
      Serial.print("\\n");
    } else if (c == '\r') {
      Serial.print("\\r");
    } else if ((uint8_t)c < 32) {
      Serial.print("\\u00");
      if ((uint8_t)c < 16) Serial.print("0");
      Serial.print((uint8_t)c, HEX);
    } else {
      Serial.print(c);
    }
  }

  Serial.print("\"");
}

void jsonPrintChar(char c) {
  String s = "";
  s += c;
  jsonPrintString(s);
}

void telemetryHello() {
  if (!settings.serialTelemetry) return;

  Serial.print("{\"v\":1,\"type\":\"hello\",\"app\":\"morsewurst\",\"device\":\"Morsewurst\",\"fw\":\"1.0\",\"mode\":\"raw_timing\"}");
  Serial.println();
}

void telemetryHeartbeat() {
  if (!settings.serialTelemetry) return;

  Serial.print("{\"v\":1,\"type\":\"heartbeat\",\"app\":\"morsewurst\",\"device\":\"Morsewurst\",\"fw\":\"1.0\",\"mode\":\"raw_timing\",\"uptime\":");
  serialPrintUint64(nowTime());
  Serial.print(",\"wpm\":");
  Serial.print(settings.wpm);
  Serial.print(",\"telemetry\":true}");
  Serial.println();
}

void telemetryToneRaw(const char* source, uint64_t t0, uint64_t t1, uint64_t duration) {
  if (!settings.serialTelemetry) return;

  Serial.print("{\"v\":1,\"type\":\"tone\",\"src\":\"");
  Serial.print(source);
  Serial.print("\",\"t0\":");
  serialPrintUint64(t0);
  Serial.print(",\"t1\":");
  serialPrintUint64(t1);
  Serial.print(",\"dur\":");
  serialPrintUint64(duration);
  Serial.print("}");
  Serial.println();
}

void telemetryToneElement(const char* source, char element, uint64_t t0, uint64_t t1, uint64_t duration) {
  if (!settings.serialTelemetry) return;

  Serial.print("{\"v\":1,\"type\":\"tone\",\"src\":\"");
  Serial.print(source);
  Serial.print("\",\"el\":");
  jsonPrintChar(element);
  Serial.print(",\"t0\":");
  serialPrintUint64(t0);
  Serial.print(",\"t1\":");
  serialPrintUint64(t1);
  Serial.print(",\"dur\":");
  serialPrintUint64(duration);

  if (strcmp(source, "iambic") == 0) {
    Serial.print(",\"unit\":");
    serialPrintUint64(iambicUnit());
  } else {
    Serial.print(",\"dit\":");
    serialPrintUint64((uint64_t)(estimatedDit + 0.5));
  }

  Serial.print(",\"wpm\":");
  Serial.print(estimatedWpm(), 1);
  Serial.print("}");
  Serial.println();
}

void addToPreview(char c) {
  if (c == '\b') {
    if (outputPreview.length() > 0) {
      outputPreview.remove(outputPreview.length() - 1);
    }
    return;
  }

  outputPreview += c;

  const int OUTPUT_PREVIEW_MAX = 21;

  if (outputPreview.length() > OUTPUT_PREVIEW_MAX) {
    outputPreview = outputPreview.substring(outputPreview.length() - OUTPUT_PREVIEW_MAX);
  }
}

void pressCombo(uint8_t modifier, char key) {
  Keyboard.press(modifier);
  Keyboard.press(key);
  delay(5);
  Keyboard.releaseAll();
}

void sendKeyboardCharFi(char c) {
  if (c >= 'A' && c <= 'Z') {
    Keyboard.print(c);
    return;
  }

  if (c >= '0' && c <= '9') {
    Keyboard.print(c);
    return;
  }

  if (c == ' ') {
    Keyboard.print(' ');
    return;
  }

  if (c == '\b') {
    Keyboard.press(KEY_BACKSPACE);
    delay(5);
    Keyboard.releaseAll();
    return;
  }

  switch (c) {
    case '.':
      Keyboard.print('.');
      break;

    case ',':
      Keyboard.print(',');
      break;

    case '?':
      pressCombo(KEY_LEFT_SHIFT, '+');
      break;

    case '!':
      pressCombo(KEY_LEFT_SHIFT, '1');
      break;

    case '/':
      pressCombo(KEY_LEFT_SHIFT, '7');
      break;

    case '(':
      pressCombo(KEY_LEFT_SHIFT, '8');
      break;

    case ')':
      pressCombo(KEY_LEFT_SHIFT, '9');
      break;

    case '&':
      pressCombo(KEY_LEFT_SHIFT, '6');
      break;

    case ':':
      pressCombo(KEY_LEFT_SHIFT, '.');
      break;

    case ';':
      pressCombo(KEY_LEFT_SHIFT, ',');
      break;

    case '=':
      pressCombo(KEY_LEFT_SHIFT, '0');
      break;

    case '+':
      Keyboard.print('+');
      break;

    case '-':
      Keyboard.print('-');
      break;

    case '_':
      pressCombo(KEY_LEFT_SHIFT, '-');
      break;

    case '"':
      pressCombo(KEY_LEFT_SHIFT, '2');
      break;

    case '@':
      pressCombo(KEY_RIGHT_ALT, '2');
      break;

    case '$':
      pressCombo(KEY_RIGHT_ALT, '4');
      break;

     case '\'':
      Keyboard.print('\'');
      break;

    default:
      break;
  }
}

void outputChar(char c) {
  addToPreview(c);

  if (settings.serialOutput && !settings.serialTelemetry) {
    if (c == '\b') {
      Serial.print("\b \b");
    } else {
      Serial.print(c);
    }
  }

  if (settings.usbKeyboard) {
    sendKeyboardCharFi(c);
  }
}

void outputText(const char* text) {
  for (int i = 0; text[i] != '\0'; i++) {
    outputChar(text[i]);
  }
}

// ======================================================
// DECODER
// ======================================================
char decodeMorse(String code) {
  if (code == "........") {
    return '\b';
  }

  if (code.length() > 8) {
    return '\0';
  }

  for (int i = 0; i < morseTableSize; i++) {
    if (code == morseTable[i].code) {
      return morseTable[i].letter;
    }
  }

  return '\0';
}

void finishLetter() {
  if (currentSymbol.length() == 0) return;

  if (currentSymbol == EASTER_EGG_CODE) {
    outputText(EASTER_EGG_TEXT);
    currentSymbol = "";
    wordSpacePrinted = false;
    requestSafeDisplayUpdate();
    return;
  }

  String finishedCode = currentSymbol;
  char decoded = decodeMorse(finishedCode);

  if (decoded != '\0') {
    outputChar(decoded);
  } else {
    if (settings.serialOutput && !settings.serialTelemetry) {
      Serial.print("[ERR:");
      Serial.print(finishedCode);
      Serial.print("]");
    }
  }

  currentSymbol = "";
  wordSpacePrinted = false;
  requestSafeDisplayUpdate();
}

void checkLetterAndWordSpace() {
  if (!settings.autoSpace) return;
  if (lastElementEnd == 0) return;

  uint64_t now = nowTime();
  uint64_t gap = now - lastElementEnd;

  double unit = estimatedDit;

  const double gapScale = 0.8;

  double letterGap = (settings.letterGapTenths / 10.0) * gapScale;
  double wordGap = (settings.wordGapTenths / 10.0) * gapScale;

  if (currentSymbol.length() > 0 && gap >= unit * letterGap) {
    finishLetter();
  }

  if (currentSymbol.length() == 0 && !wordSpacePrinted && gap >= unit * wordGap) {
    outputChar(' ');
    wordSpacePrinted = true;
  }
}

void updateDitEstimate(uint64_t pressDuration) {
  if (pressDuration < MAX_REASONABLE_DIT) {
    estimatedDit = estimatedDit * 0.85 + (double)pressDuration * 0.15;
  }
}

void addStraightElement(uint64_t pressStart, uint64_t pressDuration) {
  if (pressDuration < MIN_PRESS) return;

  if (currentSymbol.length() >= 18) {
    currentSymbol = "";
    lastElementEnd = nowTime();
    wordSpacePrinted = false;
    requestSafeDisplayUpdate();
    return;
  }

  double threshold = estimatedDit * 2.2;

  char element;

  if ((double)pressDuration < threshold) {
    element = '.';
    currentSymbol += element;
    updateDitEstimate(pressDuration);
  } else {
    element = '-';
    currentSymbol += element;
  }

  uint64_t t1 = pressStart + pressDuration;
  telemetryToneRaw("straight", pressStart, t1, pressDuration);
  
  lastElementEnd = t1;
  wordSpacePrinted = false;
  requestSafeDisplayUpdate();
}

void addIambicElement(char element, uint64_t elementStart, uint64_t elementEnd) {
  estimatedDit = (double)iambicUnit();

  uint64_t duration = elementEnd - elementStart;

  telemetryToneElement("iambic", element, elementStart, elementEnd, duration);

  if (currentSymbol.length() >= 18) {
    currentSymbol = "";
  }

  currentSymbol += element;

  lastElementEnd = elementEnd;
  wordSpacePrinted = false;
  requestSafeDisplayUpdate();
}

// ======================================================
// STRAIGHT KEY
// ======================================================
void handleStraightKey(bool straightPressed) {
  if (!settings.straightEnabled) {
    audioStop();
    lastStraightState = false;
    return;
  }

  if (straightPressed && !lastStraightState) {
    straightDownStart = nowTime();
    audioStart();
  }

  if (!straightPressed && lastStraightState) {
    uint64_t endTime = nowTime();
    audioStop();

    uint64_t duration = endTime - straightDownStart;
    addStraightElement(straightDownStart, duration);
  }

  lastStraightState = straightPressed;
}

// ======================================================
// IAMBIC
// ======================================================
bool ditPressedNow() {
  int pin = settings.swapPaddles ? DAH_PIN : DIT_PIN;
  return digitalRead(pin) == LOW;
}

bool dahPressedNow() {
  int pin = settings.swapPaddles ? DIT_PIN : DAH_PIN;
  return digitalRead(pin) == LOW;
}

bool keyerBusy() {
  if (audioActive) return true;
  if (digitalRead(STRAIGHT_KEY_PIN) == LOW) return true;
  if (ditPressedNow()) return true;
  if (dahPressedNow()) return true;
  if (lastStraightState) return true;
  if (queuedDit || queuedDah) return true;

  return false;
}

void sampleOppositePaddleDuringElement(char currentElement) {
  bool ditPressed = ditPressedNow();
  bool dahPressed = dahPressedNow();

  if (currentElement == '.' && dahPressed) {
    queuedDah = true;
  }

  if (currentElement == '-' && ditPressed) {
    queuedDit = true;
  }
}

void toneWithIambicSampling(uint64_t duration, char currentElement) {
  uint64_t start = nowTime();

  audioStart();

  while (nowTime() - start < duration) {
    sampleOppositePaddleDuringElement(currentElement);
    delayMicroseconds(150);
  }

  audioStop();
}

void silenceWithIambicSampling(uint64_t duration, char currentElement) {
  uint64_t start = nowTime();

  while (nowTime() - start < duration) {
    sampleOppositePaddleDuringElement(currentElement);
    delayMicroseconds(150);
  }
}

void sendIambicElement(char element) {
  queuedDit = false;
  queuedDah = false;

  uint64_t unit = iambicUnit();

  if (element == '.') {
    uint64_t t0 = nowTime();
    toneWithIambicSampling(unit, '.');
    uint64_t t1 = nowTime();

    addIambicElement('.', t0, t1);
    silenceWithIambicSampling(unit, '.');

    nextIambicDit = false;
  } else {
    uint64_t t0 = nowTime();
    toneWithIambicSampling(unit * 3ULL, '-');
    uint64_t t1 = nowTime();

    addIambicElement('-', t0, t1);
    silenceWithIambicSampling(unit, '-');

    nextIambicDit = true;
  }
}

char chooseCurrentPressedElement() {
  bool ditPressed = ditPressedNow();
  bool dahPressed = dahPressedNow();

  if (ditPressed && dahPressed) {
    return nextIambicDit ? '.' : '-';
  }

  if (ditPressed) return '.';
  if (dahPressed) return '-';

  return '\0';
}

void handleIambic() {
  if (!settings.iambicEnabled) return;

  char elementToSend = chooseCurrentPressedElement();

  if (elementToSend == '\0') {
    return;
  }

  sendIambicElement(elementToSend);
}

void handleQueuedIambicChange() {
  if (!settings.iambicEnabled) {
    queuedDit = false;
    queuedDah = false;
    return;
  }

  if (settings.iambicMode == 0 && !ditPressedNow() && !dahPressedNow()) {
    queuedDit = false;
    queuedDah = false;
    return;
  }

  if (queuedDit) {
    sendIambicElement('.');
    return;
  }

  if (queuedDah) {
    sendIambicElement('-');
    return;
  }
}

// ======================================================
// SETTINGS SAVE / LOAD
// ======================================================
void saveSettings() {
  prefs.begin("morse", false);

  prefs.putInt("wpm", settings.wpm);
  prefs.putInt("tone", settings.toneHz);

  prefs.putInt("dto", settings.displayTimeoutIndex);

  prefs.putInt("lgap", settings.letterGapTenths);
  prefs.putInt("wgap", settings.wordGapTenths);

  prefs.putBool("usb", settings.usbKeyboard);
  prefs.putBool("ser", settings.serialOutput);
  prefs.putBool("tel", settings.serialTelemetry);
  prefs.putBool("iam", settings.iambicEnabled);
  prefs.putBool("str", settings.straightEnabled);
  prefs.putBool("sid", settings.sidetoneEnabled);
  prefs.putBool("pho", settings.headphonesOnly);
  prefs.putBool("asp", settings.autoSpace);
  prefs.putBool("swp", settings.swapPaddles);

  prefs.putInt("imode", settings.iambicMode);

  prefs.end();
}

void loadSettings() {
  prefs.begin("morse", true);

  settings.wpm = prefs.getInt("wpm", settings.wpm);
  settings.toneHz = prefs.getInt("tone", settings.toneHz);

  settings.displayTimeoutIndex = prefs.getInt("dto", settings.displayTimeoutIndex);

  settings.letterGapTenths = prefs.getInt("lgap", settings.letterGapTenths);
  settings.wordGapTenths = prefs.getInt("wgap", settings.wordGapTenths);

  settings.usbKeyboard = prefs.getBool("usb", settings.usbKeyboard);
  settings.serialOutput = prefs.getBool("ser", settings.serialOutput);
  settings.serialTelemetry = prefs.getBool("tel", settings.serialTelemetry);
  settings.iambicEnabled = prefs.getBool("iam", settings.iambicEnabled);
  settings.straightEnabled = prefs.getBool("str", settings.straightEnabled);
  settings.sidetoneEnabled = prefs.getBool("sid", settings.sidetoneEnabled);
  settings.headphonesOnly = prefs.getBool("pho", settings.headphonesOnly);
  settings.autoSpace = prefs.getBool("asp", settings.autoSpace);
  settings.swapPaddles = prefs.getBool("swp", settings.swapPaddles);

  settings.iambicMode = prefs.getInt("imode", settings.iambicMode);

  prefs.end();

  settings.wpm = constrain(settings.wpm, 5, 60);
  settings.toneHz = constrain(settings.toneHz, 300, 1000);
  settings.iambicMode = constrain(settings.iambicMode, 0, 1);
  settings.displayTimeoutIndex =
    constrain(settings.displayTimeoutIndex, 0, DISPLAY_TIMEOUT_COUNT - 1);

  settings.letterGapTenths = constrain(settings.letterGapTenths, 20, 40);
  settings.wordGapTenths = constrain(settings.wordGapTenths, 50, 90);
}

void resetDefaults() {
  settings = Settings();
  saveSettings();
}

// ======================================================
// MENU
// ======================================================
ScreenMode screenMode = SCREEN_HOME;

MenuItem menuItems[] = {
  {"Back", MENU_ACTION_BACK, -1, 0, 0, 0},

  {"USB Keyboard", MENU_BOOL, SET_USB_KEYBOARD, 0, 0, 0},
  {"Serial Out", MENU_BOOL, SET_SERIAL_OUTPUT, 0, 0, 0},
  {"Telemetry", MENU_BOOL, SET_SERIAL_TELEMETRY, 0, 0, 0},

  {"Iambic Key", MENU_BOOL, SET_IAMBIC, 0, 0, 0},
  {"Straight Key", MENU_BOOL, SET_STRAIGHT, 0, 0, 0},

  {"Sidetone", MENU_BOOL, SET_SIDETONE, 0, 0, 0},
  {"Phones Only", MENU_BOOL, SET_HEADPHONES_ONLY, 0, 0, 0},

  {"Auto Space", MENU_BOOL, SET_AUTOSPACE, 0, 0, 0},
  {"Letter Gap", MENU_INT, SET_LETTER_GAP, 20, 40, 1},
  {"Word Gap", MENU_INT, SET_WORD_GAP, 50, 90, 1},

  {"Swap Paddles", MENU_BOOL, SET_SWAP_PADDLES, 0, 0, 0},

  {"WPM", MENU_INT, SET_WPM, 5, 60, 1},
  {"Tone Hz", MENU_INT, SET_TONE, 300, 1000, 10},

  {"Disp. Timeout", MENU_LIST, SET_DISPLAY_TIMEOUT, 0, DISPLAY_TIMEOUT_COUNT - 1, 1},

  {"Iambic Mode", MENU_LIST, SET_IAMBIC_MODE, 0, 1, 1},

  {"About", MENU_ACTION_ABOUT, -1, 0, 0, 0},
  
  {"Save Settings", MENU_ACTION_SAVE, -1, 0, 0, 0},
  {"Reset Defaults", MENU_ACTION_RESET, -1, 0, 0, 0}
};

const int menuCount = sizeof(menuItems) / sizeof(menuItems[0]);

int menuIndex = 0;
int menuTop = 0;

int aboutTop = 0;

const char ABOUT_TEXT[] =
  "Morsewurst 1.0\n\n"
  "Software written in C++ by Kasperi Koski.\n\n"
  "In Finland, good Morse keyers and practice devices are not always easy to find, especially ones that can turn keying practice into readable text on a computer screen. This can make learning and practising Morse code unnecessarily difficult at times.\n\n"
  "This project began as a hobby project while I was waiting for a K1EL keyer kit to arrive in the mail. I already had two Morse keys, but I wanted to build something of my own: a device that could send clear, accurate, raw timing data to a computer, so I could finally see what I was actually keying at the telemetry level.\n\n"
  "I have always liked devices where the user is not locked into one narrow way of working. I like controls, settings, raw data, and the feeling that every adjustment has a real purpose. Morsewurst was built with that idea in mind. It is not meant to be a formal, standards-first keyer for every possible radio use, but a practice device that helps the user learn Morse code, understand their timing, and see what goes right and wrong.\n\n"
  "Together with the Python-based Morsewurst training software, the ESP32 device, firmware, and desktop program are designed to make Morse practice visible and measurable. The whole system is also meant to be cheap, understandable, and possible to build by hand, so that even younger or newer hobbyists could eventually make one themselves.\n\n"
  "The name Morsewurst comes from Morse code and from the developer's unusually persistent fondness for sausage, a subject that has not gone entirely unnoticed by family members. It is a slightly silly name, but it fits a homemade Morse device that was never meant to take itself too seriously.\n\n"
  "Morsewurst includes adjustable settings for speed, tone, keying mode, sidetone, spacing, paddle direction, display timeout, serial output, and USB keyboard output.\n\n"
  "Originally created as a Morse keyer for the Xiegu VK-5 straight key and the Xiegu VK-6 iambic key. After a few beers, however, it should work with just about any Morse key that behaves itself reasonably well.\n\n"
  "Built on the Adafruit ESP32-S3 Feather microcontroller, using a 128x64 OLED display with U8g2. Audio is generated as an LEDC square-wave sidetone.\n\n"
  "May the operator have good practice sessions with this sausage-inspired Morse device before the end of the world arrives.\n\n"
  "A certain ancient chant may reveal a hidden conversion message when the dit is keyed seventeen times in a row.\n\n"
  "Press knob to return.";

const int ABOUT_MAX_LINES = 200;
String aboutLines[ABOUT_MAX_LINES];
int aboutLineCount = 0;

unsigned long lastDisplayUpdate = 0;
const unsigned long DISPLAY_INTERVAL_MS = 120;

unsigned long lastTelemetryHeartbeatMs = 0;
const unsigned long TELEMETRY_HEARTBEAT_INTERVAL_MS = 5000;

bool displayAwake = true;
bool displayUpdatePending = false;
unsigned long lastUserActivityMs = 0;

// ======================================================
// SETTING ACCESS
// ======================================================
bool getBoolSetting(int id) {
  switch (id) {
    case SET_USB_KEYBOARD:
      return settings.usbKeyboard;

    case SET_SERIAL_OUTPUT:
      return settings.serialOutput;

    case SET_SERIAL_TELEMETRY:
      return settings.serialTelemetry;

    case SET_IAMBIC:
      return settings.iambicEnabled;

    case SET_STRAIGHT:
      return settings.straightEnabled;

    case SET_SIDETONE:
      return settings.sidetoneEnabled;

    case SET_HEADPHONES_ONLY:
      return settings.headphonesOnly;

    case SET_AUTOSPACE:
      return settings.autoSpace;

    case SET_SWAP_PADDLES:
      return settings.swapPaddles;
  }

  return false;
}

void setBoolSetting(int id, bool value) {
  switch (id) {
    case SET_USB_KEYBOARD:
      settings.usbKeyboard = value;
      break;

    case SET_SERIAL_OUTPUT:
      settings.serialOutput = value;
      break;

    case SET_SERIAL_TELEMETRY:
      settings.serialTelemetry = value;
      break;

    case SET_IAMBIC:
      settings.iambicEnabled = value;
      break;

    case SET_STRAIGHT:
      settings.straightEnabled = value;
      break;

    case SET_SIDETONE:
      settings.sidetoneEnabled = value;
      break;

    case SET_HEADPHONES_ONLY:
      settings.headphonesOnly = value;
      break;

    case SET_AUTOSPACE:
      settings.autoSpace = value;
      break;

    case SET_SWAP_PADDLES:
      settings.swapPaddles = value;
      break;
  }
}

int getIntSetting(int id) {
  switch (id) {
    case SET_WPM:
      return settings.wpm;

    case SET_TONE:
      return settings.toneHz;

    case SET_IAMBIC_MODE:
      return settings.iambicMode;

    case SET_LETTER_GAP:
      return settings.letterGapTenths;

    case SET_WORD_GAP:
      return settings.wordGapTenths;

    case SET_DISPLAY_TIMEOUT:
      return settings.displayTimeoutIndex;
  }

  return 0;
}

void setIntSetting(int id, int value) {
  switch (id) {
    case SET_WPM:
      settings.wpm = constrain(value, 5, 60);
      estimatedDit = (double)iambicUnit();
      break;

    case SET_TONE:
      settings.toneHz = constrain(value, 300, 1000);

      if (audioActive) {
        ledcWriteTone(AUDIO_PIN, settings.toneHz);
      }

      break;

    case SET_IAMBIC_MODE:
      settings.iambicMode = constrain(value, 0, 1);
      break;

     case SET_LETTER_GAP:
      settings.letterGapTenths = constrain(value, 20, 40);
      break;
    
    case SET_WORD_GAP:
      settings.wordGapTenths = constrain(value, 50, 90);
      break;

    case SET_DISPLAY_TIMEOUT:
      settings.displayTimeoutIndex =
        constrain(value, 0, DISPLAY_TIMEOUT_COUNT - 1);
      break;
  }
}

String boolText(bool value) {
  return value ? "ON" : "OFF";
}

String tenthsText(int value) {
  String text = String(value / 10);
  text += ".";
  text += String(value % 10);
  return text;
}

String iambicModeText() {
  return settings.iambicMode == 0 ? "Mode A" : "Mode B";
}

String listValueText(int id) {
  if (id == SET_IAMBIC_MODE) return iambicModeText();
  if (id == SET_DISPLAY_TIMEOUT) return displayTimeoutText();
  return "";
}

String menuValueText(const MenuItem& item) {
  if (item.type == MENU_BOOL) {
    return boolText(getBoolSetting(item.settingId));
  }

  if (item.type == MENU_INT) {
    if (item.settingId == SET_LETTER_GAP) {
      return tenthsText(settings.letterGapTenths);
    }

    if (item.settingId == SET_WORD_GAP) {
      return tenthsText(settings.wordGapTenths);
    }

    return String(getIntSetting(item.settingId));
  }

  if (item.type == MENU_LIST) {
    return listValueText(item.settingId);
  }

  return "";
}

String currentModeText() {
  if (settings.iambicEnabled && settings.straightEnabled) return "I+S";
  if (settings.iambicEnabled) return "IAMB";
  if (settings.straightEnabled) return "STR";
  return "OFF";
}

// ======================================================
// OLED DRAWING
// ======================================================
void drawHeader(const char* title) {
  u8g2.setFont(u8g2_font_helvB10_tr);
  u8g2.setCursor(0, 12);
  u8g2.print(title);
  u8g2.drawHLine(0, 15, 128);
}

void drawHome() {
  u8g2.clearBuffer();

  drawHeader("Morsewurst 1.0");

  u8g2.setFont(u8g2_font_helvB14_tr);
  u8g2.setCursor(0, 32);
  u8g2.print(settings.wpm);
  u8g2.print(" WPM");

  u8g2.setFont(u8g2_font_6x10_tr);

  u8g2.setCursor(86, 25);
  u8g2.print(currentModeText());

  u8g2.setCursor(86, 36);
  u8g2.print(settings.toneHz);
  u8g2.print("Hz");

  u8g2.setCursor(86, 47);
  u8g2.print("SQ");

  u8g2.setCursor(0, 54);
  u8g2.print("Code ");
  u8g2.print(currentSymbol);

  u8g2.setCursor(0, 64);
  u8g2.print(outputPreview);

  u8g2.sendBuffer();
}

void drawMenu() {
  if (menuIndex < menuTop) {
    menuTop = menuIndex;
  }

  if (menuIndex > menuTop + 4) {
    menuTop = menuIndex - 4;
  }

  u8g2.clearBuffer();

  drawHeader("Menu");

  u8g2.setFont(u8g2_font_6x10_tr);

  for (int row = 0; row < 5; row++) {
    int idx = menuTop + row;
    int y = 27 + row * 9;

    if (idx >= menuCount) break;

    if (idx == menuIndex) {
      u8g2.drawBox(0, y - 8, 128, 9);
      u8g2.setDrawColor(0);
    } else {
      u8g2.setDrawColor(1);
    }

    u8g2.setCursor(2, y);
    u8g2.print(idx == menuIndex ? ">" : " ");
    u8g2.print(menuItems[idx].label);

    String value = menuValueText(menuItems[idx]);

    if (value.length() > 0) {
      int valueWidth = u8g2.getStrWidth(value.c_str());
      u8g2.setCursor(126 - valueWidth, y);
      u8g2.print(value);
    }

    u8g2.setDrawColor(1);
  }

  u8g2.sendBuffer();
}

void drawEdit() {
  MenuItem item = menuItems[menuIndex];

  u8g2.clearBuffer();

  drawHeader("Edit");

  u8g2.setFont(u8g2_font_helvB12_tr);
  u8g2.setCursor(0, 36);
  u8g2.print(item.label);

  String value = "";

  if (item.type == MENU_BOOL) {
    value = boolText(getBoolSetting(item.settingId));
  }

  if (item.type == MENU_INT) {
    if (item.settingId == SET_LETTER_GAP) {
      value = tenthsText(settings.letterGapTenths);
    } else if (item.settingId == SET_WORD_GAP) {
      value = tenthsText(settings.wordGapTenths);
    } else {
      value = String(getIntSetting(item.settingId));
    }
  }

  if (item.type == MENU_LIST) {
    value = listValueText(item.settingId);
  }

  u8g2.setFont(u8g2_font_helvB14_tr);
  u8g2.setCursor(0, 60);
  u8g2.print(value);

  u8g2.sendBuffer();
}

void addAboutLine(String line) {
  if (aboutLineCount >= ABOUT_MAX_LINES) return;

  aboutLines[aboutLineCount] = line;
  aboutLineCount++;
}

void buildAboutLines() {
  aboutLineCount = 0;

  u8g2.setFont(u8g2_font_6x10_tr);

  const int maxWidth = 128;
  String word = "";
  String line = "";

  for (int i = 0; ABOUT_TEXT[i] != '\0'; i++) {
    char c = ABOUT_TEXT[i];

    if (c == '\n') {
      if (word.length() > 0) {
        String testLine = line;

        if (testLine.length() > 0) {
          testLine += " ";
        }

        testLine += word;

        if (u8g2.getStrWidth(testLine.c_str()) <= maxWidth) {
          line = testLine;
        } else {
          addAboutLine(line);
          line = word;
        }

        word = "";
      }

      addAboutLine(line);
      line = "";

      if (ABOUT_TEXT[i + 1] == '\n') {
        addAboutLine("");
        i++;
      }

      continue;
    }

    if (c == ' ') {
      if (word.length() > 0) {
        String testLine = line;

        if (testLine.length() > 0) {
          testLine += " ";
        }

        testLine += word;

        if (u8g2.getStrWidth(testLine.c_str()) <= maxWidth) {
          line = testLine;
        } else {
          addAboutLine(line);
          line = word;
        }

        word = "";
      }

      continue;
    }

    word += c;
  }

  if (word.length() > 0) {
    String testLine = line;

    if (testLine.length() > 0) {
      testLine += " ";
    }

    testLine += word;

    if (u8g2.getStrWidth(testLine.c_str()) <= maxWidth) {
      line = testLine;
    } else {
      addAboutLine(line);
      line = word;
    }
  }

  if (line.length() > 0) {
    addAboutLine(line);
  }
}

void drawAbout() {
  if (aboutTop < 0) {
    aboutTop = 0;
  }

  int maxTop = aboutLineCount - 5;

  if (maxTop < 0) {
    maxTop = 0;
  }

  if (aboutTop > maxTop) {
    aboutTop = maxTop;
  }

  u8g2.clearBuffer();

  drawHeader("About");

  u8g2.setFont(u8g2_font_6x10_tr);

  for (int row = 0; row < 5; row++) {
    int idx = aboutTop + row;
    int y = 27 + row * 9;

    if (idx >= aboutLineCount) break;

    u8g2.setCursor(0, y);
    u8g2.print(aboutLines[idx]);
  }

  u8g2.sendBuffer();
}

void drawMessage(const char* line1, const char* line2) {
  u8g2.clearBuffer();

  u8g2.setFont(u8g2_font_helvB12_tr);
  u8g2.setCursor(0, 26);
  u8g2.print(line1);

  u8g2.setFont(u8g2_font_helvB10_tr);
  u8g2.setCursor(0, 48);
  u8g2.print(line2);

  u8g2.sendBuffer();
}

void requestDisplayUpdate() {
  lastDisplayUpdate = 0;
}

void requestSafeDisplayUpdate() {
  displayUpdatePending = true;
}

void updateDisplay() {
  if (!displayAwake) return;
  if (keyerBusy()) return;

  bool intervalReached = millis() - lastDisplayUpdate >= DISPLAY_INTERVAL_MS;

  if (!intervalReached && !displayUpdatePending) {
    return;
  }

  displayUpdatePending = false;
  lastDisplayUpdate = millis();

  if (screenMode == SCREEN_HOME) {
    drawHome();
  } else if (screenMode == SCREEN_MENU) {
    drawMenu();
  } else if (screenMode == SCREEN_ABOUT) {
    drawAbout();
  } else {
    drawEdit();
  }
}

// ======================================================
// UI CONTROL
// ======================================================
void enterMenu() {
  screenMode = SCREEN_MENU;
  menuIndex = 0;
  menuTop = 0;
  requestDisplayUpdate();
}

void exitMenu() {
  screenMode = SCREEN_HOME;
  saveSettings();
  requestDisplayUpdate();
}

void enterAbout() {
  screenMode = SCREEN_ABOUT;
  aboutTop = 0;
  buildAboutLines();
  requestDisplayUpdate();
}

void exitAbout() {
  screenMode = SCREEN_MENU;
  requestDisplayUpdate();
}

void handleHomeInput(int steps, bool pressed) {
  if (steps != 0) {
    settings.wpm = constrain(settings.wpm + steps, 5, 60);
    estimatedDit = (double)iambicUnit();
    requestDisplayUpdate();
  }

  if (pressed) {
    enterMenu();
  }
}

void handleMenuInput(int steps, bool pressed) {
  if (steps != 0) {
    menuIndex = constrain(menuIndex + steps, 0, menuCount - 1);
    requestDisplayUpdate();
  }

  if (!pressed) return;

  MenuItem item = menuItems[menuIndex];

  if (item.type == MENU_ACTION_BACK) {
    exitMenu();
    return;
  }

  if (item.type == MENU_ACTION_SAVE) {
    saveSettings();
    drawMessage("Settings saved", "OK");
    delay(650);
    requestDisplayUpdate();
    return;
  }

  if (item.type == MENU_ACTION_RESET) {
    resetDefaults();
    drawMessage("Defaults loaded", "Saved");
    delay(650);
    requestDisplayUpdate();
    return;
  }

  if (item.type == MENU_ACTION_ABOUT) {
    enterAbout();
    return;
  }

  if (item.type == MENU_BOOL) {
    screenMode = SCREEN_EDIT_BOOL;
  }

  if (item.type == MENU_INT) {
    screenMode = SCREEN_EDIT_INT;
  }

  if (item.type == MENU_LIST) {
    screenMode = SCREEN_EDIT_LIST;
  }

  requestDisplayUpdate();
}

void handleEditInput(int steps, bool pressed) {
  MenuItem item = menuItems[menuIndex];

  if (steps != 0) {
    if (item.type == MENU_BOOL) {
      setBoolSetting(item.settingId, !getBoolSetting(item.settingId));
    }

    if (item.type == MENU_INT) {
      int value = getIntSetting(item.settingId);
      value += steps * item.step;
      value = constrain(value, item.minVal, item.maxVal);
      setIntSetting(item.settingId, value);
    }

    if (item.type == MENU_LIST) {
      int value = getIntSetting(item.settingId);
      value += steps;

      if (value < item.minVal) {
        value = item.maxVal;
      }

      if (value > item.maxVal) {
        value = item.minVal;
      }

      setIntSetting(item.settingId, value);
    }

    requestDisplayUpdate();
  }

  if (pressed) {
    saveSettings();
    screenMode = SCREEN_MENU;
    requestDisplayUpdate();
  }
}

void handleAboutInput(int steps, bool pressed) {
  if (steps != 0) {
    int maxTop = aboutLineCount - 5;

    if (maxTop < 0) {
      maxTop = 0;
    }

    aboutTop = constrain(aboutTop + steps, 0, maxTop);
    requestDisplayUpdate();
  }

  if (pressed) {
    exitAbout();
  }
}

void handleUi() {
  updateEncoder();
  updateButton();

  int steps = getEncoderSteps();
  bool pressed = consumeButtonPress();

  if (steps != 0 || pressed) {
    wakeDisplay();
  }

  if (displayAwake) {
    if (screenMode == SCREEN_HOME) {
      handleHomeInput(steps, pressed);
    } else if (screenMode == SCREEN_MENU) {
      handleMenuInput(steps, pressed);
    } else if (screenMode == SCREEN_ABOUT) {
      handleAboutInput(steps, pressed);
    } else {
      handleEditInput(steps, pressed);
    }
  
    updateDisplay();
  }
}

void wakeDisplay() {
  lastUserActivityMs = millis();

  if (!displayAwake) {
    displayAwake = true;
    u8g2.setPowerSave(0);
    requestDisplayUpdate();
  }
}

unsigned long displaySleepMs() {
  int index = constrain(settings.displayTimeoutIndex, 0, DISPLAY_TIMEOUT_COUNT - 1);
  return DISPLAY_TIMEOUT_VALUES[index];
}

void checkDisplaySleep() {
  if (!displayAwake) return;

  if (millis() - lastUserActivityMs >= displaySleepMs()) {
    displayAwake = false;
    u8g2.setPowerSave(1);
  }
}

String displayTimeoutText() {
  int index = constrain(settings.displayTimeoutIndex, 0, DISPLAY_TIMEOUT_COUNT - 1);
  return String(DISPLAY_TIMEOUT_LABELS[index]);
}

// ======================================================
// SETUP
// ======================================================
void setup() {
  Serial.begin(115200);

  if (TFT_I2C_POWER >= 0) {
    pinMode(TFT_I2C_POWER, OUTPUT);
    digitalWrite(TFT_I2C_POWER, HIGH);
    delay(10);
  }

  pinMode(AUDIO_PIN, OUTPUT);
  digitalWrite(AUDIO_PIN, LOW);

  pinMode(STRAIGHT_KEY_PIN, INPUT_PULLUP);
  pinMode(DIT_PIN, INPUT_PULLUP);
  pinMode(DAH_PIN, INPUT_PULLUP);

  pinMode(ENC_CLK_PIN, INPUT_PULLUP);
  pinMode(ENC_DT_PIN, INPUT_PULLUP);
  pinMode(ENC_SW_PIN, INPUT_PULLUP);

  pinMode(HEADPHONE_DETECT_PIN, INPUT_PULLUP);

  int msb = digitalRead(ENC_CLK_PIN);
  int lsb = digitalRead(ENC_DT_PIN);
  lastEncState = (msb << 1) | lsb;
  loadSettings();

  Wire.begin();
  Wire.setClock(400000);

  u8g2.begin();
  drawMessage("Morsewurst 1.0", "Ladataan...");

  audioConfigure();

  USB.begin();
  Keyboard.begin();

  estimatedDit = (double)iambicUnit();

  delay(USB_START_DELAY_MS);

  if (settings.serialTelemetry) {
    telemetryHello();
  } else if (settings.serialOutput) {
    Serial.println();
    Serial.println("Morse ESP32-S3 HID keyboard ready");
    Serial.println("OLED display ready via U8g2");
    Serial.println("Audio waveform: square only");
  }

  lastUserActivityMs = millis();
  displayAwake = true;
  u8g2.setPowerSave(0);

  requestDisplayUpdate();
}

// ======================================================
// LOOP
// ======================================================
void loop() {
  bool straightPressed = digitalRead(STRAIGHT_KEY_PIN) == LOW;
  bool ditPressed = ditPressedNow();
  bool dahPressed = dahPressedNow();

  static bool wasAnyKeyPressed = false;

  bool anyKeyPressed = straightPressed || ditPressed || dahPressed;

  if (anyKeyPressed && !wasAnyKeyPressed) {
    wakeDisplay();
  }

  wasAnyKeyPressed = anyKeyPressed;

  if (straightPressed || lastStraightState) {
    queuedDit = false;
    queuedDah = false;
    handleStraightKey(straightPressed);
  } else {
    if (queuedDit || queuedDah) {
      handleQueuedIambicChange();
    } else {
      handleIambic();
    }
  }

  if (!straightPressed && !ditPressed && !dahPressed && !queuedDit && !queuedDah) {
    checkLetterAndWordSpace();
  }

  checkDisplaySleep();

  if (
    settings.serialTelemetry &&
    !keyerBusy() &&
    millis() - lastTelemetryHeartbeatMs >= TELEMETRY_HEARTBEAT_INTERVAL_MS
  ) {
    lastTelemetryHeartbeatMs = millis();
    telemetryHeartbeat();
  }

  handleUi();
}
