import os
from dotenv import load_dotenv
import litellm

load_dotenv(override=True)
os.environ.pop("OPENAI_BASE_URL", None)
api_key = os.getenv("OPENAI_API_KEY")
print(f"Key used: {api_key[:10]}...")

try:
    response = litellm.completion(
        model="gemini/gemini-1.5-pro",
        messages=[{"role": "user", "content": "Hello"}],
        api_key=api_key
    )
    print("Success!")
    print(response)
except Exception as e:
    print(f"Error: {e}")
