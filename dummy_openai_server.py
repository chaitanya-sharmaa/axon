from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import json
import logging

app = FastAPI()
logging.basicConfig(level=logging.INFO)

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    messages = body.get("messages", [])
    model = body.get("model", "gpt-4o-mini")
    
    print(f"\n[DUMMY LLM] 📥 Received Request for model: {model}")
    print(f"[DUMMY LLM] 📨 Total Messages: {len(messages)}")
    
    is_healing_request = False
    for msg in messages:
        content = msg.get("content", "")
        # Check if Axon is asking us to fix JSON
        if "The JSON was invalid. Fix this syntax error" in content:
            is_healing_request = True
            print(f"[DUMMY LLM] 🏥 JSON Healing Request Detected! Axon intercepted a crash.")

    # 1. Test JSON Healing
    # If the client requested JSON format, and this is NOT a healing request,
    # we INTENTIONALLY return broken JSON to trigger Axon's JSON Healer.
    if body.get("response_format", {}).get("type") == "json_object" and not is_healing_request:
        print(f"[DUMMY LLM] 😈 Returning intentionally broken JSON to test Axon's Healer...")
        return JSONResponse({
            "id": "chatcmpl-broken",
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '{"status": "success", "data": [1, 2, 3,] }' # Trailing comma!
                },
                "finish_reason": "stop"
            }]
        })
    
    if is_healing_request:
        print(f"[DUMMY LLM] 🩹 Returning FIXED JSON...")
        return JSONResponse({
            "id": "chatcmpl-fixed",
            "object": "chat.completion",
            "model": model,
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '{"status": "success", "data": [1, 2, 3]}' # Fixed!
                },
                "finish_reason": "stop"
            }]
        })

    # 2. Normal Response
    return JSONResponse({
        "id": "chatcmpl-123",
        "object": "chat.completion",
        "model": model,
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 10,
            "total_tokens": 110
        },
        "choices": [{
            "message": {
                "role": "assistant",
                "content": "This is a successful response from the simulated LLM."
            },
            "finish_reason": "stop"
        }]
    })

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=9090, log_level="error")
