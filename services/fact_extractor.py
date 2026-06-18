import os
import json
import httpx
import logging
from typing import Any

log = logging.getLogger(__name__)

async def extract_facts_async(session_id: str, message: str, api_key: str, memory_store: Any) -> None:
    """
    Background worker that distills raw chat messages into permanent facts.
    Uses a highly compressed output format to minimize token bloat on future injections.
    """
    if not message or len(message) < 10:
        return  # Ignore trivial messages

    model = os.getenv("AXON_EXTRACTION_MODEL", "gpt-4o-mini")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    
    if not api_key:
        api_key = os.getenv("OPENAI_API_KEY", "")

    # We enforce JSON mode or strict parsing to get an array of strings
    system_prompt = (
        "Extract any persistent facts, preferences, or entity properties from the user's message. "
        "Format your output strictly as a JSON array of very short, dense strings. "
        "Use key=value or shorthand if possible to save tokens (e.g. ['user_name=alice', 'lang=python']). "
        "If there are no new facts, output an empty array []."
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"} if "gpt" in model else None
    }
    
    # We will just parse the array normally if we can't use json_object for an array.
    # Actually, json_object requires an object. So we ask for `{"facts": [...]}`.
    system_prompt = (
        "Extract persistent facts/preferences. Output strictly a JSON object: {\"facts\": [\"user=alice\", \"lang=python\"]}. "
        "If none, output {\"facts\": []}."
    )
    payload["messages"][0]["content"] = system_prompt

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload
            )
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                
                try:
                    result = json.loads(content)
                    facts = result.get("facts", [])
                    if facts:
                        # Ensure the session exists in the DB so foreign keys don't fail
                        await memory_store.create_session(session_id)
                    for fact in facts:
                        if isinstance(fact, str):
                            await memory_store.add_session_fact(session_id, fact)
                            log.debug(f"Extracted fact for {session_id}: {fact}")
                except json.JSONDecodeError:
                    log.warning("Fact extraction returned invalid JSON.")
                    
        except Exception as e:
            log.warning(f"Failed to extract facts in background: {e}")
