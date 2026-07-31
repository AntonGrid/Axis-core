import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

from jsonschema import Draft7Validator, ValidationError


BASE_DIR = Path(__file__).resolve().parent
SCHEMAS_DIR = BASE_DIR / "schemas"


@lru_cache(maxsize=None)
def load_schema(name: str) -> Dict[str, Any]:
    """Load a JSON Schema from the schemas/ directory.

    name: base name without extension, e.g. "device_record".
    """
    schema_path = SCHEMAS_DIR / f"{name}.schema.json"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    with schema_path.open("r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def get_validator(name: str) -> Draft7Validator:
    schema = load_schema(name)
    return Draft7Validator(schema)


def validate_payload(name: str, payload: Dict[str, Any]) -> None:
    """Validate payload against a named schema.

    Raises ValidationError on failure.
    """
    validator = get_validator(name)
    validator.validate(payload)
