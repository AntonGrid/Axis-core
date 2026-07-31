import json
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def load_attestation_schema() -> dict:
    base_dir = Path(__file__).resolve().parent.parent
    schema_path = base_dir / "schemas" / "attestation.schema.json"
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)
