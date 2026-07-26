#include "identity.h"

#include <Preferences.h>     // стандартная NVS-обёртка ESP32
#include <ArduinoJson.h>

// ВАЖНО: вам понадобится библиотека Ed25519 для Arduino/ESP32.
// Пример: https://github.com/TrustWallet/TrustWalletCore/tree/master/src/Private/Ed25519
// Здесь используются абстрактные функции ed25519_create_keypair и ed25519_sign,
// которые вы должны связать с конкретной библиотекой.

extern "C" {
    void ed25519_create_keypair(uint8_t* pubkey, uint8_t* privkey, const uint8_t* seed);
    void ed25519_sign(uint8_t* sig, const uint8_t* msg, size_t msg_len,
                      const uint8_t* pub_key, const uint8_t* priv_key);
}

// ---------- Константы хранения в NVS ----------

static const char* NVS_NAMESPACE = "identity";
static const char* KEY_PRIV      = "privkey";   // 32 байта seed либо 64 байта sk (зависит от реализации)
static const char* KEY_PUB       = "pubkey";    // 32 байта
static const char* KEY_DEVICE_ID = "device_id"; // строка base58
static const char* KEY_MANIFEST  = "manifest";  // строка manifest_version

static Preferences prefs;
static DeviceIdentity g_identity;
static bool g_identity_initialized = false;

// ---------- Вспомогательные функции (base58 + sha256) ----------

#include <mbedtls/sha256.h>

static String to_hex(const uint8_t* data, size_t len) {
    static const char hex_chars[] = "0123456789abcdef";
    String out;
    out.reserve(len * 2);
    for (size_t i = 0; i < len; ++i) {
        out += hex_chars[(data[i] >> 4) & 0x0F];
        out += hex_chars[data[i] & 0x0F];
    }
    return out;
}

// Простейшая base58-реализация можно подключить как отдельную либу.
// Здесь объявим прототип и ожидаем, что вы подключите реализацию.
String base58_encode(const uint8_t* data, size_t len);

static String compute_device_id_from_pubkey(const uint8_t* pubkey32) {
    uint8_t hash[32];
    mbedtls_sha256(pubkey32, 32, hash, 0 /*is224*/);
    return base58_encode(hash, 32);
}

// ---------- Реализация публичного API ----------

bool identity_init() {
    if (g_identity_initialized) {
        return true;
    }

    prefs.begin(NVS_NAMESPACE, false /* RW */);

    size_t privLen = prefs.getBytesLength(KEY_PRIV);
    size_t pubLen  = prefs.getBytesLength(KEY_PUB);

    uint8_t privkey[64] = {0};

    if (privLen > 0 && pubLen == 32) {
        // Ключи уже есть — загружаем
        prefs.getBytes(KEY_PUB, g_identity.publicKey, 32);
        prefs.getBytes(KEY_PRIV, privkey, sizeof(privkey));

        String storedDeviceId = prefs.getString(KEY_DEVICE_ID, "");
        if (storedDeviceId.length() > 0) {
            g_identity.deviceId = storedDeviceId;
        } else {
            g_identity.deviceId = compute_device_id_from_pubkey(g_identity.publicKey);
            prefs.putString(KEY_DEVICE_ID, g_identity.deviceId);
        }
    } else {
        // Ключей нет — генерируем
        // seed можно взять из аппаратного RNG
        uint8_t seed[32];
        for (int i = 0; i < 32; ++i) {
            seed[i] = (uint8_t)esp_random();
        }

        ed25519_create_keypair(g_identity.publicKey, privkey, seed);

        // Сохраняем в NVS
        prefs.putBytes(KEY_PUB, g_identity.publicKey, 32);
        prefs.putBytes(KEY_PRIV, privkey, sizeof(privkey));

        g_identity.deviceId = compute_device_id_from_pubkey(g_identity.publicKey);
        prefs.putString(KEY_DEVICE_ID, g_identity.deviceId);
    }

    g_identity_initialized = true;
    return true;
}

DeviceIdentity get_device_identity() {
    if (!g_identity_initialized) {
        identity_init();
    }
    return g_identity;
}

bool sign_message(const uint8_t* msg, size_t msgLen, uint8_t* sigOut) {
    if (!g_identity_initialized) {
        identity_init();
    }

    uint8_t privkey[64] = {0};
    size_t privLen = prefs.getBytes(KEY_PRIV, privkey, sizeof(privkey));
    if (privLen == 0) {
        return false;
    }

    ed25519_sign(sigOut, msg, msgLen, g_identity.publicKey, privkey);
    return true;
}

const char* get_firmware_version() {
#ifndef FW_VERSION
#define FW_VERSION "1.0.0-dev"
#endif
    return FW_VERSION;
}

String get_manifest_version() {
    prefs.begin(NVS_NAMESPACE, true /* readOnly */);
    return prefs.getString(KEY_MANIFEST, "");
}

void set_manifest_version(const String& manifestVersion) {
    prefs.begin(NVS_NAMESPACE, false /* RW */);
    prefs.putString(KEY_MANIFEST, manifestVersion);
}
