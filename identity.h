#pragma once

#include <Arduino.h>
#include <stdint.h>

// Структура с публичной идентичностью устройства
struct DeviceIdentity {
    String deviceId;       // base58(sha256(public_key))
    uint8_t publicKey[32]; // Ed25519 публичный ключ
};

// Инициализация подсистемы идентичности.
// Вызывается из setup():
//  - пытается загрузить ключи из NVS
//  - если не находит — генерирует новую пару Ed25519 и сохраняет
bool identity_init();

// Получить текущую идентичность устройства (device_id + public key)
DeviceIdentity get_device_identity();

// Подписать произвольное сообщение буфером bytes длиной msgLen.
// sigOut должен указывать на буфер длиной 64 байта (Ed25519 подпись).
// Возвращает true при успехе.
bool sign_message(const uint8_t* msg, size_t msgLen, uint8_t* sigOut);

// Вспомогательная функция: получить firmware version, зашитую в прошивку
// (можно определить FW_VERSION в platformio.ini или вверху .ino файла).
const char* get_firmware_version();

// Вспомогательная функция: получить текущую manifest_version,
// сохранённую в NVS (или пустую строку, если ещё не применён).
String get_manifest_version();

// Установить manifest_version и сохранить её в NVS после успешного применения Manifest.
void set_manifest_version(const String& manifestVersion);
