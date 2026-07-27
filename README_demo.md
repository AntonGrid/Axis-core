# ENRG demo: от Attestation до on-chain calldata

Этот репозиторий содержит несколько небольших демо-скриптов, которые показывают полный путь:

- от оффлайн-JSON до on-chain параметров,
- от оффлайн-JSON до calldata для `submitAttestation`,
- от онлайн-оракула до полной Attestation и её on-chain представления,
- а также отказной (deny) сценарий с `allowed = false`.

## Предварительные условия

- Python 3.x
- Виртуальное окружение с зависимостями (`pip install -r requirements.txt`)
- (для онлайн-сценариев) Запущенный ENRG backend:

```bash
uvicorn app.main:app --reload --port 8000
По умолчанию backend слушает http://localhost:8000.

1. Оффлайн: JSON → on-chain параметры
Сценарий: есть готовый attestation-example.json в корне репозитория. Нужно посмотреть, какие on-chain параметры из него получаются для контракта:

submitAttestation(
  bytes32 attestationId,
  bytes32 deviceId,
  bool allowed,
  uint64 maxPowerW,
  uint64 issuedAt
)
Скрипт: scripts/demo_onchain_bridge.py

Запуск:

python scripts/demo_onchain_bridge.py
Ожидаемый вывод (примерно):

=== On-chain parameters for submitAttestation ===
attestationId (bytes32): 0x...
deviceId      (bytes32): 0x...
allowed       (bool)   : True
maxPowerW     (uint64) : 2500
issuedAt      (uint64) : 1785006300
Что делает скрипт:

читает attestation-example.json,
при необходимости добавляет "schema_version": "1.0",
вызывает build_attestation_params(attestation),
печатает готовые on-chain аргументы.
2. Оффлайн: JSON → on-chain параметры → calldata
Сценарий: есть attestation-example.json, нужно не только посмотреть параметры, но и получить готовый calldata для вызова submitAttestation(...).

Скрипт: scripts/send_attestation_onchain.py

Запуск:

python scripts/send_attestation_onchain.py \
  --attestation-file attestation-example.json
Пример вывода (сокращённо):

=== On-chain parameters for submitAttestation ===
attestationId (bytes32): 0x...
deviceId      (bytes32): 0x...
allowed       (bool)   : True
maxPowerW     (uint64) : 2500
issuedAt      (uint64) : 1785006300

=== Calldata for submitAttestation ===
0x44b67025...
Что делает скрипт:

парсит JSON как Attestation (с schema_version: "1.0"),
использует build_attestation_params для вычисления on-chain параметров,
ABI-кодирует аргументы с сигнатурой: submitAttestation(bytes32,bytes32,bool,uint64,uint64),
печатает итоговый calldata, который можно использовать в EOF-транзакции или CLI-инструменте.
3. Онлайн (happy-path): oracle → Attestation → on-chain параметры → calldata
Сценарий: полный happy-path от живого backend-а до calldata.

Проверяем /health.
Делаем запрос к /oracle/attest (новый формат).
Собираем полную Attestation, совместимую с attestation.schema.json (с schema_version: "1.0").
Получаем on-chain параметры через build_attestation_params.
Строим calldata для submitAttestation.
Скрипт: scripts/full_oracle_onchain_calldata_demo.py

Запуск (при запущенном backend):

python scripts/full_oracle_onchain_calldata_demo.py \
  --device-id dev_demo_full_cycle \
  --max-power-kw 3.3
Пример вывода (обрезано):

=== Step 1: /health ===
{
  "status": "ok"
}

=== Step 2: POST /oracle/attest (new format) ===
{
  "device_id": "dev_demo_full_cycle",
  "attestation_id": "...",
  "decision": {
    "allowed": true,
    "reason": "ok",
    "max_power_kw": 3.3
  }
}

=== Step 3: Build full Attestation from oracle response ===
{
  "schema_version": "1.0",
  "attestation_id": "...",
  "device_id": "dev_demo_full_cycle",
  "proof": { ... },
  "decision": {
    "allowed": true,
    "reason": "ok",
    "max_power_kw": 3.3
  },
  "oracle_id": "oracle_main_1",
  "issued_at": "...",
  "oracle_signature": "..."
}

=== Step 4: Build on-chain params via build_attestation_params ===
On-chain parameters for submitAttestation:
  attestationId (bytes32): 0x...
  deviceId      (bytes32): 0x...
  allowed       (bool)   : True
  maxPowerW     (uint64) : 3300
  issuedAt      (uint64) : 1785130443

=== Step 5: Build calldata for submitAttestation ===
0x44b67025...
Скрипт не отправляет транзакцию, а только печатает параметры и calldata.

4. Онлайн (deny-case): oracle (allowed=false) → Attestation → on-chain параметры → calldata
Сценарий: демонстрация отказного пути, когда allowed = false.

Вызываем /health.
Делаем запрос к /oracle/attest с такими параметрами, при которых оракул возвращает отказ (например, max_power_kw выше лимита).
На основе ответа строим полную Attestation с schema_version: "1.0".
Дополнительно фиксируем причину отказа в человекочитаемом виде (reason = "overridden-to-deny-demo"), сохраняя при этом allowed = false.
Прогоняем Attestation через build_attestation_params.
Строим calldata для вызова submitAttestation с allowed = false.
Скрипт: scripts/oracle_deny_onchain_calldata_demo.py

Пример запуска (при запущенном backend):

python scripts/oracle_deny_onchain_calldata_demo.py \
  --device-id dev_demo_deny \
  --max-power-kw 10.0
Пример ответа оракула и построенной Attestation (обрезано):

=== Step 2: POST /oracle/attest (new format) ===
{
  "device_id": "dev_demo_deny",
  "attestation_id": "dfb9...",
  "decision": {
    "allowed": false,
    "reason": "max_power_exceeded",
    "max_power_kw": 10.0,
    "limit_kw": 5.0
  }
}

=== Step 3: Build full *deny* Attestation from oracle response ===
{
  "schema_version": "1.0",
  "attestation_id": "dfb9...",
  "device_id": "dev_demo_deny",
  "proof": { ... },
  "decision": {
    "allowed": false,
    "reason": "overridden-to-deny-demo",
    "max_power_kw": 10.0
  },
  "oracle_id": "oracle_main_1",
  "issued_at": "...",
  "oracle_signature": "..."
}
Ончейн-параметры и calldata (обрезано):

=== Step 4: Build on-chain params via build_attestation_params ===
On-chain parameters for submitAttestation (deny-case):
  attestationId (bytes32): 0x9d9a63...
  deviceId      (bytes32): 0xe46a23...
  allowed       (bool)   : False
  maxPowerW     (uint64) : 10000
  issuedAt      (uint64) : 1785130731

=== Step 5: Build calldata for submitAttestation (deny-case) ===
0x44b670259d9a63...
Комментарии:

Оракул уже сам возвращает allowed: false (например, при превышении лимита мощности).
Скрипт строит итоговую Attestation, совместимую со схемой 1.0, и дополнительно фиксирует причину отказа (reason = "overridden-to-deny-demo"), чтобы явно показать, что это демонстрационный deny-кейс.
Далее используется тот же on-chain путь, что и в happy-path: build_attestation_params + ABI-кодирование submitAttestation(...).
Скрипт не шлёт транзакцию, а только печатает calldata с allowed = false — его можно использовать в EOF-транзакции или CLI-туле для демонстрации отказного кейса.

Краткое резюме демо-скриптов
scripts/demo_onchain_bridge.py
Оффлайн: Attestation JSON → on-chain параметры.

scripts/send_attestation_onchain.py
Оффлайн: Attestation JSON → on-chain параметры → calldata submitAttestation(...).

scripts/full_oracle_onchain_calldata_demo.py
Онлайн happy-path: /oracle/attest (allowed = true) → полная Attestation (schema_version: "1.0") → on-chain параметры → calldata.

scripts/oracle_deny_onchain_calldata_demo.py
Онлайн deny-case: /oracle/attest (allowed = false) → полная Attestation (schema_version: "1.0") с явным reason для отказа → on-chain параметры → calldata с allowed = false.

