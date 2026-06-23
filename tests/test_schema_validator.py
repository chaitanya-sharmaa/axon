import pytest
import json
from services.schema_validator import SchemaValidator

def test_schema_validator_no_schema():
    validator = SchemaValidator()
    is_valid, err, parsed = validator.validate_output('{"a": 1}', None)
    assert is_valid is True
    assert err is None
    assert parsed is None

def test_schema_validator_invalid_json():
    validator = SchemaValidator()
    schema = {"type": "object"}
    is_valid, err, parsed = validator.validate_output('{bad json', schema)
    assert is_valid is False
    assert "Output is not valid JSON" in err
    assert parsed is None

def test_schema_validator_valid_schema():
    validator = SchemaValidator()
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"}
        },
        "required": ["name"]
    }
    is_valid, err, parsed = validator.validate_output('{"name": "Alice", "age": 30}', schema)
    assert is_valid is True
    assert err is None
    assert parsed == {"name": "Alice", "age": 30}

def test_schema_validator_invalid_schema():
    validator = SchemaValidator()
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"}
        },
        "required": ["name", "age"]
    }
    # Missing required field "age"
    is_valid, err, parsed = validator.validate_output('{"name": "Alice"}', schema)
    assert is_valid is False
    assert "fails schema validation" in err
    assert "age" in err or "required" in err
    assert parsed == {"name": "Alice"}
