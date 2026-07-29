// Новая версия прошивки отправки proof с использованием уникального ключа
// и device_id, привязанного к публичному ключу.

#define FW_VERSION "1.0.0-enrg"

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

#include "identity.h"

// TODO: укажите реальные значения
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// URL сервера Oracle/Proof-инжестера
const char* PROOF_ENDPOINT = "https://your-oracle.example.com/proofs";

unsigned long lastReportMs = 0;
unsigned long reportIntervalMs = 60 * 1000; // по умолчанию 60 секунд, может быть переопределено Manifest

static uint32_t g_nonce = 0;

// Заглушка функции измерения энергии.
// Замените на реальное чтение с датчика/счётчика.
float read_energy_wh() {
    // TODO: реальная логика измерения
    return 123.45f;
}

void connect_wifi() {
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println(" connected");
}

void send_proof() {
    DeviceIdentity id = get_device_identity();

    float energyWh = read_energy_wh();
    uint32_t nowTs = (uint32_t)(millis() / 1000); // Замените на реальное время (NTP/RTC) для продакшена

    // Готовим JSON payload
    StaticJsonDocument<512> payload;
    payload["device_id"]        = id.deviceId;
    payload["timestamp"]        = nowTs;
    payload["nonce"]            = g_nonce++;
    payload["energy_wh"]        = energyWh;
    payload["firmware_version"] = get_firmware_version();
    payload["manifest_version"] = get_manifest_version();

    String payloadStr;
    serializeJson(payload, payloadStr);

    // Подписываем payload
    uint8_t sig[64];
    if (!sign_message((const uint8_t*)payloadStr.c_str(), payloadStr.length(), sig)) {
        Serial.println("[ERROR] Failed to sign proof payload");
        return;
    }

    // кодируем сигнатуру в base64
    String sigBase64 = base64::encode(sig, sizeof(sig));

    StaticJsonDocument<768> root;
    root["payload"]   = payload;
    root["signature"] = sigBase64;

    String body;
    serializeJson(root, body);

    if (WiFi.status() != WL_CONNECTED) {
        connect_wifi();
    }

    HTTPClient http;
    http.begin(PROOF_ENDPOINT);
    http.addHeader("Content-Type", "application/json");

    int httpCode = http.POST(body);
    if (httpCode > 0) {
        Serial.printf("[INFO] Proof sent, response code: %d\n", httpCode);
        String resp = http.getString();
        Serial.println(resp);
    } else {
        Serial.printf("[ERROR] Failed to send proof, error: %s\n", http.errorToString(httpCode).c_str());
    }

    http.end();
}

void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("\n[BOOT] ENRG Proof Sender v2");

    if (!identity_init()) {
        Serial.println("[FATAL] identity_init failed");
        while (true) {
            delay(1000);
        }
    }

    DeviceIdentity id = get_device_identity();
    Serial.print("Device ID: ");
    Serial.println(id.deviceId);

    connect_wifi();
}

void loop() {
    unsigned long now = millis();
    if (now - lastReportMs >= reportIntervalMs) {
        lastReportMs = now;
        send_proof();
    }

    // Здесь можно добавить обработку входящих команд / обновлений Manifest
    delay(10);
}
