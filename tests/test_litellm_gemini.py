import os
from dotenv import load_dotenv
import litellm

load_dotenv(override=True)
os.environ.pop("OPENAI_BASE_URL", None)
api_key = os.getenv("OPENAI_API_KEY")
print(f"OPENAI_API_KEY present: {bool(api_key)}")

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
