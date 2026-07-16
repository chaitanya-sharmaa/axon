from services.schema_validator import schema_validator
import json

schema = {
    "type": "object", 
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"}
    },
    "required": ["name"]
}

print(schema_validator.validate_output(json.dumps({"name": "test", "age": 20}), schema))
