# ENRG Onchain

Этот модуль содержит on‑chain часть системы ENRG:

- смарт‑контракт `EnrgOracleAttestation` для хранения аттестаций устройств;
- Foundry‑конфиг и тесты;
- скрипты для локального развёртывания и end‑to‑end демо.

Контракт позволяет доверенным оракулам публиковать аттестации устройств с ограничением по мощности и временем выпуска.

---

## Структура

- `src/EnrgOracleAttestation.sol` — основной контракт.
- `script/` — скрипты для Foundry (если используются).
- `test/` — тесты Foundry.
- `scripts/` — утилиты и демо‑скрипты на Python (например, `send_attestation_onchain.py`).
- `foundry.toml` — конфигурация Foundry.

---

## Быстрый старт с Foundry

### Установка зависимостей

Предполагается, что Foundry уже установлен. Если нет, см. инструкции на https://book.getfoundry.sh/.

Проверка:

```bash
forge --version
anvil --version
cast --version
Запуск тестов
cd ~/ENRG/onchain
forge test
Локальный запуск сети (Anvil)
Для локальной разработки и демо используется Anvil — локальная Ethereum‑сеть.

cd ~/ENRG/onchain
anvil
Anvil поднимает сеть на http://127.0.0.1:8545 с преднастроенными аккаунтами и приватными ключами (выводится в консоль Anvil).

Деплой контракта EnrgOracleAttestation
В отдельном терминале (при уже запущенном Anvil):

cd ~/ENRG/onchain

forge create src/EnrgOracleAttestation.sol:EnrgOracleAttestation \
  --rpc-url http://127.0.0.1:8545 \
  --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  --broadcast
В конце вывода будет строка вида:

Deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
Этот адрес контракта будем использовать дальше как CONTRACT.

Работа с контрактом через cast
Проверить owner
CONTRACT=0x5FbDB2315678afecb367f032d93F642f64180aa3
RPC=http://127.0.0.1:8545

cast call $CONTRACT "owner()(address)" --rpc-url $RPC
Ожидается адрес первого аккаунта Anvil:

0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Отметить trusted oracle
Используем тот же адрес как доверенный oracle:

OWNER=0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266
PK=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

cast send $CONTRACT \
  "setTrustedOracle(address,bool)" \
  $OWNER true \
  --rpc-url $RPC \
  --private-key $PK
Проверка:

cast call $CONTRACT \
  "trustedOracles(address)(bool)" \
  $OWNER \
  --rpc-url $RPC
# должно вернуть: true
End‑to‑end demo: отправка аттестации в контракт
Этот раздел показывает полный цикл:

запуск локальной сети через Anvil;
деплой контракта EnrgOracleAttestation;
установка trusted oracle;
отправка JSON‑аттестации из Python‑скрипта в контракт.
1. Запуск Anvil
В одном терминале:

cd ~/ENRG/onchain
anvil
Anvil поднимает сеть на http://127.0.0.1:8545 с преднастроенными аккаунтами.

2. Деплой контракта
Во втором терминале:

cd ~/ENRG/onchain

forge create src/EnrgOracleAttestation.sol:EnrgOracleAttestation \
  --rpc-url http://127.0.0.1:8545 \
  --private-key 0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80 \
  --broadcast
В конце вывода будет строка:

Deployed to: 0x5FbDB2315678afecb367f032d93F642f64180aa3
Скопируйте этот адрес контракта и подставьте его в переменную CONTRACT ниже.

3. Python‑окружение
Создайте и активируйте виртуальное окружение (один раз):

cd ~/ENRG/onchain
python3 -m venv .venv
source .venv/bin/activate
pip install web3
Дальнейшие команды предполагают активированное .venv. При каждом новом открытии терминала:

cd ~/ENRG/onchain
source .venv/bin/activate
4. Переменные окружения
Во втором терминале (где .venv):

export CONTRACT=0x5FbDB2315678afecb367f032d93F642f64180aa3  # адрес из forge create
export RPC=http://127.0.0.1:8545
export PK=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

export ENRG_ORACLE_CONTRACT_ADDRESS=$CONTRACT
export ENRG_RPC_URL=$RPC
export ENRG_PRIVATE_KEY=$PK
Проверьте:

echo $ENRG_ORACLE_CONTRACT_ADDRESS
# должно вывести адрес контракта
5. Установка trusted oracle
Адрес первого аккаунта Anvil:

OWNER=0xf39fd6e51aad88f6f4ce6ab8827279cfffb92266

cast send $CONTRACT \
  "setTrustedOracle(address,bool)" \
  $OWNER true \
  --rpc-url $RPC \
  --private-key $PK

cast call $CONTRACT \
  "trustedOracles(address)(bool)" \
  $OWNER \
  --rpc-url $RPC
# должно вернуть: true
6. E2E‑скрипт: scripts/send_attestation_onchain.py
Скрипт scripts/send_attestation_onchain.py формирует JSON‑аттестацию, конвертирует её в on‑chain формат и вызывает submitAttestation на контракте.

Запуск (в активированном .venv):

cd ~/ENRG/onchain
python scripts/send_attestation_onchain.py
Пример вывода:

Using RPC: http://127.0.0.1:8545
Using account: 0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266
Contract: 0x5FbDB2315678afecb367f032d93F642f64180aa3
Attestation JSON:
{'attestation_id': 'attestation-e2e-1', 'device_id': 'device-e2e-abc', 'decision': {'allowed': True, 'max_power_kw': 500.0}, 'issued_at': '2026-07-26T14:15:00Z'}
On-chain params:
  attestation_id: 88b2f210858d89623f5da82f0a7198cfb98cfd7eb2c5bff32292af8cc776d678
  device_id:      bc1d10ed6f4670881c8963fa64e15516c5125e9bbbc928a20ddc404c8da24b34
  allowed:        True
  max_power_w:    500000
  issued_at:      1785075300
Submitted tx: 0c5c9e66c2575340680f5dc6f73ed5bc7326eb84ba763bd0b0c542cac25db384
Tx status: 1
Gas used: 140932
Stored attestation in contract:
[b'\x88\xb2\xf2\x10\x85\x8d\x89b?]\xa8/\nq\x98\xcf\xb9\x8c\xfd~\xb2\xc5\xbf\xf3"\x92\xaf\x8c\xc7v\xd6x',
 b'\xbc\x1d\x10\xedoFp\x88\x1c\x89c\xfad\xe1U\x16\xc5\x12^\x9b\xbb\xc9(\xa2\r\xdc@L\x8d\xa2K4',
 True,
 500000,
 '0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266',
 1785075300]
Это подтверждает, что JSON‑аттестация успешно конвертируется и записывается в контракт EnrgOracleAttestation в локальной сети Anvil.
