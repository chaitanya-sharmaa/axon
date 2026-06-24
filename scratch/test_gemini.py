import os
import requests

api_key = os.getenv("OPENAI_API_KEY", "REDACTED_API_KEY")
headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
payload = {"contents": [{"role": "user", "parts": [{"text": "Hello"}]}]}
url = "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent"
resp = requests.post(url, headers=headers, json=payload)
print(f"gemini-2.5-flash v1: {resp.status_code}")
if resp.status_code != 200:
    print(resp.text)
else:
    print("SUCCESS")
