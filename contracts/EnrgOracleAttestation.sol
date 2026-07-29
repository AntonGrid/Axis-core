// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title ENRG Oracle Attestation Contract (minimal skeleton)
/// @notice Принимает attestations от доверенных оракулов и эмитит события.
contract EnrgOracleAttestation {
    /// @dev Доверенные оракулы (обычно адреса, за которыми стоят off-chain-сервисы Oracle).
    mapping(address => bool) public isTrustedOracle;

    /// @dev Адрес владельца контракта (временно — централизованный админ / DAO-мультисиг).
    address public owner;

    /// @notice Attestation о состоянии/решении по устройству.
    struct Attestation {
        bytes32 deviceId;       // Хэш/байтовое представление device_id ("dev_...")
        address oracle;         // Адрес оракула (msg.sender)
        bool allowed;           // Разрешено ли действие/режим
        int96 maxPowerKw;       // Макс. мощность * 1e6 (фиксированная точность)
        uint64 issuedAt;        // Unix timestamp выпуска аттестации
        bytes32 proofHash;      // Хэш исходного DeviceProof/Attestation JSON (off-chain хранится отдельно)
    }

    /// @dev Событие, которое будут слушать другие контракты / off-chain клиенты.
    event DeviceAttested(
        bytes32 indexed deviceId,
        address indexed oracle,
        bool allowed,
        int96 maxPowerKw,
        uint64 issuedAt,
        bytes32 proofHash
    );

    /// @dev Эмитится при добавлении/удалении доверенного оракула.
    event TrustedOracleUpdated(address indexed oracle, bool isTrusted);

    error NotOwner();
    error NotTrustedOracle();

    constructor(address _owner) {
        owner = _owner;
    }

    /// @notice Обновляет статус доверенного оракула.
    /// @dev В проде это будет управляться DAO / мультисигом.
    function setTrustedOracle(address oracle, bool trusted) external {
        if (msg.sender != owner) revert NotOwner();
        isTrustedOracle[oracle] = trusted;
        emit TrustedOracleUpdated(oracle, trusted);
    }

    /// @notice Приём аттестации от доверенного оракула.
    /// @param deviceId Хэш/байтовое представление `device_id` (например, keccak256("dev_9e9c...")).
    /// @param allowed Разрешено ли действие.
    /// @param maxPowerKw Макс. мощность * 1e6 (для дробной части без float).
    /// @param issuedAt Unix timestamp выпуска аттестации.
    /// @param proofHash keccak256 от сериализованного Attestation/DeviceProof JSON.
    function submitAttestation(
        bytes32 deviceId,
        bool allowed,
        int96 maxPowerKw,
        uint64 issuedAt,
        bytes32 proofHash
    ) external {
        if (!isTrustedOracle[msg.sender]) revert NotTrustedOracle();

        // Здесь можно добавить доп. проверки (например, что issuedAt не слишком в прошлом/будущем).

        emit DeviceAttested(deviceId, msg.sender, allowed, maxPowerKw, issuedAt, proofHash);
    }
}
