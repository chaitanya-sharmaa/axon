import json
import logging
from typing import Any

import jsonschema
from jsonschema.exceptions import ValidationError

log = logging.getLogger(__name__)

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
            jsonschema.validate(instance=parsed, schema=schema)
            return True, None, parsed
        except ValidationError as e:
            # We provide a concise error message for the LLM to heal
            err_msg = f"JSON matches syntax but fails schema validation: at path {'/'.join([str(p) for p in e.path]) if e.path else 'root'} - {e.message}"
            log.warning(f"SchemaValidator: {err_msg}")
            return False, err_msg, parsed

schema_validator = SchemaValidator()
