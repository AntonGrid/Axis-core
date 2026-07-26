# ENRG

ENRG — экспериментальный прототип архитектуры для управления устройствами и их аттестациями с минимальным on-chain слоем.

Цель: зафиксировать **chain-agnostic** подход, где:

- корень доверия — ключ на устройстве;
- off-chain слой отвечает за идентичность, Provisioning, Registry, Policy Engine и Oracle;
- on-chain слой минимален и опирается на attestations от доверенных оракулов.

## Структура репозитория

- `app/` — off-chain сервисы (FastAPI) и вспомогательный код:
  - Provisioning Service;
  - Device Registry;
  - Oracle (`/oracle/attest`, хранение аттестаций);
  - `onchain_bridge.py` — мост JSON → параметры смарт-контракта.
- `tests/` — pytest‑тесты для off-chain кода.
- `schemas/` — JSON Schema для:
  - `DeviceManifest`;
  - `DeviceRecord`;
  - `DeviceProof`;
  - `Attestation`.
- `attestation-example.json` — пример аттестации Oracle.
- `scripts/` — вспомогательные скрипты:
  - `demo_onchain_bridge.py` — демонстрация маппинга off-chain → on-chain.
- `onchain/` — минимальный on-chain слой (Foundry):
  - `src/EnrgOracleAttestation.sol` — контракт для приёма аттестаций;
  - `test/EnrgOracleAttestation.t.sol` — тесты к контракту;
  - `onchain/README.md` — описание контрактов и тестов.
- `docs/`:
  - `onchain-attestation.md` — спецификация маппинга Attestation JSON → параметры `submitAttestation`.

## Off-chain слой (Python / FastAPI)

Основные компоненты:

- **Provisioning Service** — регистрирует устройства, создаёт `DeviceRecord`.
- **Device Registry** — источник истины по устройствам:
  - `device_id`, ключи, владелец, состояние жизненного цикла, версия прошивки, `manifest_ref`.
- **Oracle**:
  - принимает `DeviceProof`;
  - применяет политику (mock Policy Engine);
  - выдаёт `Attestation` с решением (`allowed`, `max_power_kw` и т.п.);
  - хранит аттестации для последующей выборки.

JSON Schema и формат артефактов описаны в `schemas/` и используются в тестах.

### Тесты off-chain

Из корня репозитория:

```bash
source .venv/bin/activate
pytest -q
Они покрывают:

регистрацию устройств;
создание и проверку DeviceProof;
работу Oracle (/oracle/attest);
хранение и чтение аттестаций;
маппинг JSON Attestation → on-chain параметры (test_onchain_bridge.py).
On-chain слой (Foundry)
Находится в каталоге onchain/.

Ключевой контракт:

EnrgOracleAttestation:

хранит минимальную структуру:

struct AttestationCore {
    bytes32 attestationId;
    bytes32 deviceId;
    bool allowed;
    uint64 maxPowerW;
    address oracle;
    uint64 issuedAt; // unix timestamp
}
принимает аттестации только от доверенных оракулов (setTrustedOracle / trustedOracles);

не позволяет записать одну и ту же attestationId дважды;

эмитит событие Attested.

Тесты на контракт:

cd onchain
forge test -q
Подробнее см. onchain/README.md.

Мост off-chain → on-chain
Маппинг Attestation JSON → параметры submitAttestation реализован в:

app/onchain_bridge.py — функция:

build_attestation_params(attestation: dict)
Она:

получает аттестацию вида attestation-example.json;
считает keccak256 от attestation_id и device_id → bytes32 значения для контракта;
конвертирует decision.max_power_kw → maxPowerW (ватты);
парсит issued_at (ISO 8601, Z) → issuedAt (unix timestamp).
Текстовая спецификация маппинга:

docs/onchain-attestation.md
Демонстрация маппинга (скрипт)
Из корня репозитория:

source .venv/bin/activate
python scripts/demo_onchain_bridge.py
Скрипт:

читает attestation-example.json;
строит параметры для смарт-контракта;
выводит готовые значения:
attestationId (bytes32): 0x...
deviceId      (bytes32): 0x...
allowed       (bool)   : true/false
maxPowerW     (uint64) : XXXX
issuedAt      (uint64) : 1XXXXXXXXX
Эти параметры соответствуют сигнатуре:

submitAttestation(
    bytes32 attestationId,
    bytes32 deviceId,
    bool allowed,
    uint64 maxPowerW,
    uint64 issuedAt
)
и могут быть напрямую использованы при вызове контракта в локальной сети (anvil, Hardhat и т.п.).

Статус
Off-chain: рабочий прототип с тестами и схемами.
On-chain: минимальный контракт с проверками и тестами в Foundry.
Мост: реализован и задокументирован.
Этот репозиторий можно использовать как основу для дальнейших итераций (Policy Engine, продвинутый Oracle, интеграция с разными сетями и т.д.).
