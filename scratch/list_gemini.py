import os
import requests
import json

api_key = os.getenv("OPENAI_API_KEY", "REDACTED_API_KEY")
headers = {"x-goog-api-key": api_key}
url = "https://generativelanguage.googleapis.com/v1beta/models"
resp = requests.get(url, headers=headers)
print(resp.status_code)
if resp.status_code == 200:
    models = resp.json().get("models", [])
    print(f"Found {len(models)} models:")
    for m in models:
        print(f"- {m.get('name')}")
else:
    print(resp.text)
