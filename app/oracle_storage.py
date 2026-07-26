# app/oracle_storage.py

class InMemoryOracleStorage:
    """
    Простая in-memory реализация хранения аттестаций Oracle.
    Используется в тестах как заглушка для долговременного хранения.
    """

    def __init__(self) -> None:
        self._store = {}

    def store_attestation(self, attestation: dict) -> None:
        """
        Сохранить аттестацию по её идентификатору.
        Требуется поле 'attestation_id' в словаре attestation.
        """
        attestation_id = attestation.get("attestation_id")
        if not attestation_id:
            raise KeyError("Missing attestation_id in attestation")
        self._store[attestation_id] = attestation

    def get_attestation(self, attestation_id: str):
        """
        Вернуть аттестацию по id или None, если не найдено.
        """
        return self._store.get(attestation_id)
