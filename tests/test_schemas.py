import json
from pathlib import Path

from jsonschema import Draft7Validator


BASE_DIR = Path(__file__).resolve().parent.parent


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_attestation_example_matches_schema():
    schema_path = BASE_DIR / "schemas" / "attestation.schema.json"
    example_path = BASE_DIR / "attestation-example.json"

    schema = load_json(schema_path)
    example = load_json(example_path)

    validator = Draft7Validator(schema)
    errors = sorted(validator.iter_errors(example), key=lambda e: e.path)

    assert not errors, f"Attestation example does not match schema: {[e.message for e in errors]}"
