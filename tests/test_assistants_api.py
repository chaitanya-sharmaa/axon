"""Test the new Axon /v1/threads Assistants API using the official OpenAI SDK."""

import os
import pytest
from openai import AsyncOpenAI
import asyncio

from dotenv import load_dotenv
load_dotenv()

# Point the official OpenAI SDK to the local Axon Proxy!
client = AsyncOpenAI(
    base_url="http://127.0.0.1:8080/v1",
    api_key=os.environ.get("OPENAI_API_KEY", os.environ.get("GEMINI_API_KEY", "dummy"))
)

@pytest.mark.asyncio
async def test_assistants_api_flow():
    # 1. Create a Thread
    print("\n[1] Creating thread...")
    thread = await client.beta.threads.create()
    assert thread.id.startswith("thread_")
    print(f"✅ Created Thread: {thread.id}")
    
    # 2. Add a message to the Thread
    print("\n[2] Adding message to thread...")
    message = await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="What is the capital of France? Reply in one word."
    )
    assert message.role == "user"
    assert message.thread_id == thread.id
    print(f"✅ Added Message: {message.id}")
    
    # 3. List messages (should be 1)
    print("\n[3] Listing messages...")
    messages = await client.beta.threads.messages.list(thread_id=thread.id)
    assert len(messages.data) == 1
    assert messages.data[0].content[0].text.value == "What is the capital of France? Reply in one word."
    print("✅ Message list verified")
    
    # 4. Run the Thread
    print("\n[4] Running thread (Calling LLM)...")
    run = await client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id="asst_dummy123", # Option A: Dummy assistant ID
        model="gemini/gemini-2.5-flash"
    )
    assert run.status == "completed"
    assert run.assistant_id == "asst_dummy123"
    print(f"✅ Run Completed: {run.id}")
    
    # 5. List messages again (should now be 2, with the assistant's reply at the top)
    print("\n[5] Verifying assistant reply...")
    messages_after = await client.beta.threads.messages.list(thread_id=thread.id)
    assert len(messages_after.data) == 2
    
    # The OpenAI SDK returns messages in descending order, so data[0] is the newest
    assistant_reply = messages_after.data[0]
    assert assistant_reply.role == "assistant"
    reply_text = assistant_reply.content[0].text.value
    print(f"✅ Assistant Reply: {reply_text}")
    
    assert "paris" in reply_text.lower()
    print("\n🎉 All standard OpenAI Assistants API methods worked perfectly through Axon!")

if __name__ == "__main__":
    asyncio.run(test_assistants_api_flow())
