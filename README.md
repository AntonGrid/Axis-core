# ENRG Part II Mock

Минимальный мок-сервис ENRG Part II.

## Запуск

1. Активировать виртуальное окружение:

cd ~/ENRG
source .venv/bin/activate

2. Запустить сервер:

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

3. Проверить, что сервис жив:

curl http://localhost:8000/health

Ожидаемый ответ: {"status": "ok"}

4. Примеры запросов

Регистрация устройства:

curl -X POST http://localhost:8000/provisioning/register \
  -H "Content-Type: application/json" \
  -d '{
    "public_key": "test-public-key-123",
    "manufacturer": "acme",
    "model": "sensor-v1"
  }'

Получить устройство из реестра:

curl http://localhost:8000/registry/devices/<device_id>

Аттестация устройства:

curl -X POST http://localhost:8000/provisioning/attest \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "<device_id>",
    "nonce": "abc12345xyz",
    "timestamp": "2026-07-25T19:00:00Z",
    "algo": "mock",
    "payload": {
      "max_power_kw": 2.5
    },
    "signature": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
  }'

## Тесты

pytest
