import asyncio
import os

import httpx
from openai import AsyncOpenAI

# Initialize standard OpenAI SDK pointed at local Axon server
client = AsyncOpenAI(
    base_url="http://localhost:8080/v1",
    api_key="dummy-key",
)

# A highly specific fact that no LLM knows
SECRET_FACT = "The secret launch code for project Antigravity is 'Tango Charlie 99', and the lead architect is named Dr. Reginald P. Fizzbottom."

async def run_rag_test():
    print("\n🚀 STARTING AXON NATIVE RAG TEST 🚀\n")

    # 1. Create a dummy text file
    with open("secret_doc.txt", "w") as f:
        f.write("CONFIDENTIAL DOCUMENT\n\n")
        f.write("This document outlines the master plan for the new project.\n")
        f.write(SECRET_FACT + "\n")
        f.write("Do not share this with anyone.\n")

    # 2. Upload file using standard HTTPX (since OpenAI SDK file upload expects openai URL sometimes,
    # but we can use the raw endpoint)
    print("[1] Uploading 'secret_doc.txt' to Axon /v1/files...")
    async with httpx.AsyncClient(timeout=30.0) as hc:
        with open("secret_doc.txt", "rb") as f:
            resp = await hc.post(
                "http://localhost:8080/v1/files",
                files={"file": ("secret_doc.txt", f, "text/plain")},
                data={"purpose": "assistants"}
            )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        file_id = resp.json()["id"]
        print(f"    File uploaded successfully! ID: {file_id}")

    # 3. Create a thread
    print("\n[2] Creating an Assistant Thread...")
    thread = await client.beta.threads.create()
    print(f"    Thread ID: {thread.id}")

    # 4. Add a message WITH the file attached
    print("\n[3] Sending a message with the file attached...")
    # Using raw httpx for message creation since OpenAI Python SDK validation might fail on our custom "attachments" format if it uses a newer spec,
    # Actually, we can use the exact format we built in our API.
    async with httpx.AsyncClient(timeout=30.0) as hc:
        msg_resp = await hc.post(
            f"http://localhost:8080/v1/threads/{thread.id}/messages",
            json={
                "role": "user",
                "content": "Who is the lead architect for project Antigravity?",
                "attachments": [{"file_id": file_id}]
            }
        )
        assert msg_resp.status_code == 200, f"Message creation failed: {msg_resp.text}"
        print("    Message added with attachment!")

    # 5. Run the thread
    print("\n[4] Executing Thread Run (Should trigger Local RAG!)...")

    print("\n[5] Waiting for LLM Response...")
    import json

    # Wait a bit (since it's a generator we'll just usehttpx to hit the raw stream and print it)
    async with httpx.AsyncClient(timeout=60.0) as hc:
        async with hc.stream("POST", f"http://localhost:8080/v1/threads/{thread.id}/runs", json={
            "assistant_id": "asst_123",
            "model": "ollama/llama3",
            "stream": True
        }) as response:
            full_text = ""
            async for line in response.aiter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    try:
                        data = json.loads(line[6:])
                        if data.get("object") == "thread.message.delta":
                            chunk = data["delta"]["content"][0]["text"]["value"]
                            full_text += chunk
                            print(chunk, end="", flush=True)
                    except:
                        pass
            print("\n")

            print("--- VERIFICATION ---")
            print(f"Full Text Output: {full_text}")
            assert "Fizzbottom" in full_text, "LLM failed to answer using RAG context!"
            print("✅ RAG successfully extracted the exact chunk and injected it into context!")

    # Cleanup
    os.remove("secret_doc.txt")

if __name__ == "__main__":
    asyncio.run(run_rag_test())
