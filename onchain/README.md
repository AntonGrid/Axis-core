# ENRG On-chain

Этот каталог содержит минимальный on-chain слой для ENRG — контракт, который принимает аттестации от доверенных оракулов.

## Структура

- `src/EnrgOracleAttestation.sol` — основной контракт.
- `test/EnrgOracleAttestation.t.sol` — тесты на контракт (Foundry).
- `README.md` — это файл.
- Остальной код (off-chain) находится в корне проекта (`app/`, `tests/`, `scripts/` и т.д.).

## Контракт: EnrgOracleAttestation

Контракт хранит минимальную информацию об аттестации устройства:

```solidity
struct AttestationCore {
    bytes32 attestationId;
    bytes32 deviceId;
    bool allowed;
    uint64 maxPowerW;
    address oracle;
    uint64 issuedAt; // unix timestamp
}
Ключевые вызовы:

function setTrustedOracle(address oracle, bool trusted) external;

function submitAttestation(
    bytes32 attestationId,
    bytes32 deviceId,
    bool allowed,
    uint64 maxPowerW,
    uint64 issuedAt
) external;
setTrustedOracle может вызывать только владелец контракта (owner).
submitAttestation могут вызывать только адреса, помеченные как доверенные оракулы.
Аттестации не могут быть записаны повторно с тем же attestationId.
Связь с off-chain слоем
Off-chain код (Python) строит параметры для submitAttestation из JSON‑аттестации Oracle.

За это отвечает функция:

app.onchain_bridge.build_attestation_params(attestation: dict)
Она:

берёт attestation["attestation_id"] и attestation["device_id"];
считает keccak256 от этих строк → bytes32 для attestationId и deviceId;
берёт decision.allowed → allowed;
берёт decision.max_power_kw и умножает на 1000 → maxPowerW (ватты);
парсит issued_at (ISO 8601, с Z) → unix timestamp issuedAt.
Подробнее описано в:

docs/onchain-attestation.md
Как прогнать тесты
Foundry (контракт)
Из корня репозитория:

cd onchain
forge test -q
Python (off-chain + мост)
Из корня репозитория:

source .venv/bin/activate
pytest -q
Демонстрация маппинга off-chain → on-chain
Из корня репозитория:

source .venv/bin/activate
python scripts/demo_onchain_bridge.py
Скрипт:

читает attestation-example.json;
прогоняет его через build_attestation_params(...);
выводит готовые параметры для вызова submitAttestation:
attestationId (bytes32): 0x...
deviceId      (bytes32): 0x...
allowed       (bool)   : true/false
maxPowerW     (uint64) : XXXX
issuedAt      (uint64) : 1XXXXXXXXX
Эти значения можно напрямую использовать в вызове контракта, деплойнутого, например, в локальной сети (anvil, Hardhat и т.п.).
