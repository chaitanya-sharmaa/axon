import json
import logging
from typing import Any, Literal

from pydantic import TypeAdapter, create_model, ValidationError

log = logging.getLogger(__name__)

def _json_schema_to_pydantic_type(schema: dict[str, Any]) -> Any:
    """Recursively converts a JSON Schema dict into a Pydantic-compatible type."""
    if not isinstance(schema, dict):
        return Any

    schema_type = schema.get("type", "any")

    # If it's a list of types (e.g. ["string", "null"]), grab the first one that isn't null
    if isinstance(schema_type, list):
        types_without_null = [t for t in schema_type if t != "null"]
        schema_type = types_without_null[0] if types_without_null else "any"

    if schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        fields = {}
        # Ensure all required fields are in properties even if not explicitly defined
        for req in required:
            if req not in properties:
                properties[req] = {"type": "any"}

        for prop_name, prop_schema in properties.items():
            prop_type = _json_schema_to_pydantic_type(prop_schema)
            # Check for enum in string or integer properties without explicit type
            if not isinstance(prop_schema, dict):
                pass
            elif "enum" in prop_schema:
                enum_values = prop_schema["enum"]
                if enum_values:
                    prop_type = Literal[tuple(enum_values)]
            
            if prop_name in required:
                fields[prop_name] = (prop_type, ...)
            else:
                fields[prop_name] = (prop_type | None, None)

        # For strict Pydantic V2 validation mimicking JSON Schema, forbid extra fields if specified?
        # Typically JSON schema allows extra unless additionalProperties is false, but Pydantic by default ignores.
        # We can just let it ignore.
        return create_model("DynamicModel", **fields)

    elif schema_type == "array":
        items_schema = schema.get("items", {})
        item_type = _json_schema_to_pydantic_type(items_schema) if items_schema else Any
        return list[item_type]

    elif schema_type == "string":
        if "enum" in schema and schema["enum"]:
            return Literal[tuple(schema["enum"])]
        return str
    elif schema_type == "integer":
        if "enum" in schema and schema["enum"]:
            return Literal[tuple(schema["enum"])]
        return int
    elif schema_type == "number":
        return float
    elif schema_type == "boolean":
        return bool
    else:
        return Any

class SchemaValidator:
    """Validates LLM outputs against strict JSON Schemas."""

    def validate_output(self, llm_output: str, schema: dict[str, Any]) -> tuple[bool, str | None, dict | None]:
        """
        Validates the output against the JSON Schema.
        Returns: (is_valid, error_message, parsed_json)
        """
        if not schema:
            return True, None, None

        try:
            parsed = json.loads(llm_output)
        except json.JSONDecodeError as e:
            return False, f"Output is not valid JSON: {str(e)}", None

        try:
            pydantic_type = _json_schema_to_pydantic_type(schema)
            ta = TypeAdapter(pydantic_type)
            # validate_python allows converting string->int if needed, 
            # and returns the parsed model/dict
            validated_model = ta.validate_python(parsed)
            # If it's a BaseModel, convert it back to dict for the caller
            if hasattr(validated_model, "model_dump"):
                parsed = validated_model.model_dump(exclude_unset=True)
            return True, None, parsed
        except ValidationError as e:
            # Format Pydantic errors for the LLM to easily understand
            err_details = []
            for err in e.errors():
                path = ".".join([str(loc) for loc in err["loc"]]) or "root"
                err_details.append(f"Field '{path}': {err['msg']}")
                
            err_msg = f"JSON matches syntax but fails schema validation: {'; '.join(err_details)}"
            log.warning(f"SchemaValidator: {err_msg}")
            return False, err_msg, parsed
        except Exception as e:
            # Fallback for dynamic model creation errors
            err_msg = f"Failed to build or validate schema: {str(e)}"
            log.warning(f"SchemaValidator: {err_msg}")
            return False, err_msg, parsed

schema_validator = SchemaValidator()
