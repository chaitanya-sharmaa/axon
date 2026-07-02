from services.tool_compressor import (
    _json_schema_to_python_type,
    compress_tools_to_prompt,
    reconstruct_tool_calls,
)


def test_json_schema_to_python_type():
    assert _json_schema_to_python_type({"type": "string"}) == "str"
    assert _json_schema_to_python_type({"type": "string", "enum": ["a", "b"]}) == "Literal['a', 'b']"
    assert _json_schema_to_python_type({"type": "integer"}) == "int"
    assert _json_schema_to_python_type({"type": "number"}) == "float"
    assert _json_schema_to_python_type({"type": "boolean"}) == "bool"
    assert _json_schema_to_python_type({"type": "array", "items": {"type": "string"}}) == "list[str]"
    assert _json_schema_to_python_type({"type": "object"}) == "Any"
    assert _json_schema_to_python_type({}) == "Any"

def test_compress_tools_to_prompt():
    assert compress_tools_to_prompt([]) == ""

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city"
                        },
                        "unit": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"]
                        }
                    },
                    "required": ["location"]
                }
            }
        },
        {
            "type": "other"  # Should be skipped
        }
    ]

    prompt = compress_tools_to_prompt(tools)
    assert "def get_weather" in prompt
    assert "location: str  # The city" in prompt
    assert "unit: Literal['celsius', 'fahrenheit'] = None" in prompt
    assert "<tool_calls>" in prompt

def test_compress_tools_to_prompt_no_desc():
    tools = [
        {
            "type": "function",
            "function": {
                "name": "simple",
                "parameters": {
                    "properties": {
                        "x": {"type": "integer"}
                    }
                }
            }
        }
    ]
    prompt = compress_tools_to_prompt(tools)
    assert "def simple(x: int = None) -> None:" in prompt

def test_reconstruct_tool_calls():
    assert reconstruct_tool_calls("") is None
    assert reconstruct_tool_calls("Normal response without tools") is None

    valid_xml = '''
Here is the result:
<tool_calls>
[
  {"name": "get_weather", "arguments": {"location": "London"}}
]
</tool_calls>
'''
    calls = reconstruct_tool_calls(valid_xml)
    assert len(calls) == 1
    assert calls[0]["type"] == "function"
    assert calls[0]["function"]["name"] == "get_weather"
    assert '"London"' in calls[0]["function"]["arguments"]
    assert "id" in calls[0]

    invalid_json = "<tool_calls>[ {bad json ]</tool_calls>"
    assert reconstruct_tool_calls(invalid_json) is None

    not_a_list = '<tool_calls>{"name": "get_weather"}</tool_calls>'
    assert reconstruct_tool_calls(not_a_list) is None
