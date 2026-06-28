import os
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from openai import AsyncOpenAI
import asyncio
from dotenv import load_dotenv
load_dotenv()

# Enable assistants routes for this test (opt-in feature)
os.environ["AXON_ENABLE_ASSISTANTS_ROUTES"] = "true"
from app import app

# Point the official OpenAI SDK to the local Axon Proxy!
client = AsyncOpenAI(
    base_url="http://testserver/v1",
    api_key=os.environ.get("OPENAI_API_KEY", os.environ.get("GEMINI_API_KEY", "dummy")),
    http_client=AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver/v1")
)

class MockResponseNonStream:
    def model_dump(self):
        return {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "ollama/llama3",
            "choices": [{"message": {"role": "assistant", "content": "Assistant reply!"}}],
            "usage": {}
        }

class MockResponseStream:
    async def __aiter__(self):
        class MockDelta:
            content = "1 2 3 4 5"
        class MockChoice:
            delta = MockDelta()
        class MockChunk:
            choices = [MockChoice()]
        yield MockChunk()

async def mock_acompletion_side_effect(*args, **kwargs):
    if kwargs.get("stream"):
        return MockResponseStream()
    return MockResponseNonStream()

@pytest.mark.asyncio
@patch("api.routes.v1_assistants_routes.litellm.acompletion", new_callable=AsyncMock)
async def test_assistants_api_flow(mock_acompletion):
    mock_acompletion.side_effect = mock_acompletion_side_effect
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
    try:
        run = await client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id="asst_dummy123",
            model="ollama/llama3"
        )
    except Exception as e:
        if hasattr(e, "response"):
            print(f"FAILED with response: {e.response.text}")
        raise e
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
    
    # 6. Test Streaming!
    print("\n[6] Testing stream=True ...")
    await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content="Now count from 1 to 5. Reply with just the numbers."
    )
    
    stream = await client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id="asst_dummy123",
        model="ollama/llama3",
        stream=True
    )
    
    print("Streaming output: ", end="", flush=True)
    async for event in stream:
        if event.event == "thread.message.delta":
            print(event.data.delta.content[0].text.value, end="", flush=True)
    print("\n✅ Stream completed successfully!")
    
    print("\n🎉 All standard OpenAI Assistants API methods (including streaming) worked perfectly through Axon!")

if __name__ == "__main__":
    asyncio.run(test_assistants_api_flow())
