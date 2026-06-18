import asyncio
import json
import logging
import os
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
import httpx
import threading
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ─── Mock OpenAI Server ───────────────────────────────────────────────────────
mock_app = FastAPI()

import hashlib

@mock_app.post("/v1/embeddings")
async def mock_embeddings(request: Request):
    body = await request.json()
    text = body.get("input", "")
    # Generate non-parallel 16-dimensional vectors based on md5 so cosine sim works properly
    h = hashlib.md5(text.encode()).digest()
    vec = []
    for i in range(16):
        vec.append((float(h[i]) / 128.0) - 1.0)
    return {"data": [{"embedding": vec}]}

@mock_app.post("/v1/chat/completions")
async def mock_chat(request: Request):
    body = await request.json()
    model = body.get("model", "")
    
    # Simulate a rate limit for gpt-4o-mini to trigger fallback
    if model == "gpt-4o-mini" and "trigger_rate_limit" in str(body):
        return JSONResponse(status_code=429, content={"error": {"message": "Rate limit exceeded"}})
        
    # Simulate fact extraction
    if body["messages"][0]["role"] == "system" and "Extract persistent facts" in body["messages"][0]["content"]:
        return {
            "choices": [{
                "message": {"content": '{"facts": ["user=alice", "lang=python"]}'}
            }]
        }
    
    # Return what we received so the test can assert on it
    return {
        "choices": [{
            "message": {
                "role": "assistant", 
                "content": "Mocked response",
                "received_model": model,
                "received_messages": body["messages"]
            }
        }]
    }

def run_mock_server():
    uvicorn.run(mock_app, host="127.0.0.1", port=8081, log_level="error")

# ─── Run Axon Server ──────────────────────────────────────────────────────────
def run_axon_server():
    os.environ["OPENAI_BASE_URL"] = "http://127.0.0.1:8081/v1"
    os.environ["AXON_AUTO_ROUTING"] = "true"
    os.environ["AXON_SEMANTIC_CACHE"] = "true"
    os.environ["OPENAI_API_KEY"] = "mock_key"
    
    # Import inside thread to pick up env vars
    from app import app
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="error")

# ─── Scenarios ────────────────────────────────────────────────────────────────
async def run_scenarios():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8080") as client:
        log.info("Waiting for servers to start...")
        for _ in range(20):
            try:
                r = await client.get("/health/live")
                if r.status_code == 200:
                    break
            except:
                await asyncio.sleep(0.5)
        else:
            log.error("Axon server failed to start.")
            sys.exit(1)
            
        log.info("Servers running! Starting complex scenarios...\n")
        
        # 1. Semantic Response Caching
        log.info("--- Scenario 1: Semantic Caching ---")
        payload = {"model": "gpt-4-turbo", "messages": [{"role": "user", "content": "What is 2+2?"}]}
        
        start = time.time()
        res1 = await client.post("/v1/chat/completions", json=payload)
        t1 = time.time() - start
        log.info(f"First request latency: {t1*1000:.0f}ms")
        
        start = time.time()
        res2 = await client.post("/v1/chat/completions", json=payload)
        t2 = time.time() - start
        
        cache_header = res2.headers.get("x-axon-cache")
        log.info(f"Second request latency: {t2*1000:.0f}ms | Cache: {cache_header}")
        assert cache_header == "HIT", "Semantic Cache did not hit!"
        log.info("✅ Semantic Caching PASSED\n")

        # 2a. Smart Down-routing
        log.info("--- Scenario 2a: Smart Down-routing ---")
        payload_small = {
            "model": "gpt-4o", 
            "messages": [{"role": "user", "content": "small payload"}]
        }
        res_small = await client.post("/v1/chat/completions", json=payload_small)
        used_model_small = res_small.json()["choices"][0]["message"]["received_model"]
        log.info(f"Requested: gpt-4o | Axon routed to: {used_model_small}")
        assert used_model_small == "gpt-4o-mini", f"Expected down-routing to gpt-4o-mini, got {used_model_small}"
        log.info("✅ Smart Down-routing PASSED\n")

        # 2b. Rate Limit Fallback
        log.info("--- Scenario 2b: Rate Limit Fallback ---")
        payload_fallback = {
            "model": "gpt-4o-mini", 
            "messages": [{"role": "user", "content": "trigger_rate_limit"}]
        }
        res3 = await client.post("/v1/chat/completions", json=payload_fallback)
        resp_data = res3.json()
        
        # We requested gpt-4o-mini, mock server returned 429, Axon should automatically retry with gpt-3.5-turbo
        used_model = resp_data["choices"][0]["message"]["received_model"]
        log.info(f"Requested: gpt-4o-mini | Upstream gave 429 | Axon fallback used: {used_model}")
        assert used_model == "gpt-3.5-turbo", f"Expected gpt-3.5-turbo fallback, got {used_model}"
        log.info("✅ Rate Limit Fallback PASSED\n")

        # 3. Intelligent Semantic Memory (Mem0-Style)
        log.info("--- Scenario 3: Intelligent Semantic Memory ---")
        session_id = "complex-e2e-session"
        headers = {"X-Session-ID": session_id}
        
        payload_mem = {
            "model": "gpt-4-turbo", 
            "messages": [{"role": "user", "content": "Hello, I am testing the new memory module."}]
        }
        await client.post("/v1/chat/completions", json=payload_mem, headers=headers)
        
        log.info("Sent initial message. Waiting 1.5s for async background fact extraction...")
        await asyncio.sleep(1.5)
        
        payload_mem2 = {
            "model": "gpt-4-turbo", 
            "messages": [{"role": "user", "content": "What was my name again?"}]
        }
        res_mem = await client.post("/v1/chat/completions", json=payload_mem2, headers=headers)
        mem_data = res_mem.json()
        
        received_messages = mem_data["choices"][0]["message"]["received_messages"]
        system_msg = received_messages[0]
        
        log.info(f"Axon injected this into the prompt: {system_msg['content']}")
        assert system_msg["role"] == "system"
        assert "Memory:" in system_msg["content"]
        assert "user=alice" in system_msg["content"], "Facts were not extracted and injected!"
        log.info("✅ Intelligent Semantic Memory PASSED\n")
        
        log.info("All complex scenarios successfully verified! Axon is robust and intelligent.")

if __name__ == "__main__":
    threading.Thread(target=run_mock_server, daemon=True).start()
    threading.Thread(target=run_axon_server, daemon=True).start()
    asyncio.run(run_scenarios())
