import os

import requests
from dotenv import load_dotenv

load_dotenv(override=True)
api_key = os.getenv("OPENAI_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-pro:generateContent?key={api_key}"

payload = {
  "contents": [{
    "parts":[{"text": "Hello, this is a test. Answer with exactly 'World'."}]
    }]
}

response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
print("Status Code:", response.status_code)
print("Response:", response.text)
