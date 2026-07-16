import os

# Initialize client
os.environ["GEMINI_API_KEY"] = "fake-key" # or whatever
from google import genai
client = genai.Client()
try:
    resp = client.models.count_tokens(model="gemini-2.0-flash", contents="Hello world!")
    print(resp.total_tokens)
except Exception as e:
    print(e)
