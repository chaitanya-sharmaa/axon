import json
import re
from typing import Any

def _json_schema_to_python_type(prop: dict[str, Any]) -> str:
    """Convert JSON Schema types to Python type hints."""
    t = prop.get("type", "Any")
    if t == "string":
        if "enum" in prop:
            return f"Literal[{', '.join(repr(x) for x in prop['enum'])}]"
        return "str"
    if t == "integer":
        return "int"
    if t == "number":
        return "float"
    if t == "boolean":
        return "bool"
    if t == "array":
        items = prop.get("items", {})
        return f"list[{_json_schema_to_python_type(items)}]"
    return "Any"

def compress_tools_to_prompt(tools: list[dict[str, Any]]) -> str:
    """
    Compresses an OpenAI verbose JSON Schema tools array into a dense Python-like string.
    This saves massive amounts of tokens on the system prompt for agentic workflows.
    """
    if not tools:
        return ""
        
    compressed_signatures = []
    
    for tool in tools:
        if tool.get("type") != "function":
            continue
            
        func = tool.get("function", {})
        name = func.get("name", "unknown")
        desc = func.get("description", "")
        
        params = func.get("parameters", {})
        properties = params.get("properties", {})
        required = params.get("required", [])
        
        args_str_list = []
        for prop_name, prop_data in properties.items():
            py_type = _json_schema_to_python_type(prop_data)
            prop_desc = prop_data.get("description", "")
            
            arg_decl = f"{prop_name}: {py_type}"
            if prop_name not in required:
                arg_decl += " = None"
                
            if prop_desc:
                arg_decl += f"  # {prop_desc}"
            
            args_str_list.append(arg_decl)
            
        args_str = ", ".join(args_str_list) if not any("#" in a for a in args_str_list) else "\n    " + ",\n    ".join(args_str_list) + "\n"
        
        signature = f"def {name}({args_str}) -> None:\n    \"\"\"{desc}\"\"\"\n    pass"
        compressed_signatures.append(signature)
        
    tools_block = "\n\n".join(compressed_signatures)
    
    system_prompt = f"""
You have access to the following tools:
```python
{tools_block}
```
If you need to use a tool, you MUST reply with EXACTLY the following XML block and nothing else:
<tool_calls>
[
  {{"name": "tool_name_here", "arguments": {{"arg1": "value1"}}}}
]
</tool_calls>
If you do not need to use a tool, just reply normally.
"""
    return system_prompt.strip()

def reconstruct_tool_calls(response_text: str) -> list[dict[str, Any]] | None:
    """
    Parses the LLM's response text to see if it hallucinated our simulated <tool_calls> block.
    If so, extracts it and converts it into the OpenAI-compatible native `tool_calls` array format.
    """
    if not response_text:
        return None
        
    match = re.search(r"<tool_calls>\s*(\[.*?\])\s*</tool_calls>", response_text, re.DOTALL)
    if not match:
        return None
        
    json_str = match.group(1)
    try:
        parsed = json.loads(json_str)
        if not isinstance(parsed, list):
            return None
            
        openai_tool_calls = []
        for idx, call in enumerate(parsed):
            openai_tool_calls.append({
                "id": f"call_{idx}_{abs(hash(response_text))}",
                "type": "function",
                "function": {
                    "name": call.get("name", ""),
                    "arguments": json.dumps(call.get("arguments", {}))
                }
            })
            
        return openai_tool_calls
    except json.JSONDecodeError:
        return None
