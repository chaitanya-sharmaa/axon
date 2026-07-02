import requests

key = "REDACTED_API_KEY"

# Test 1: Is it Google OpenAI compatible?
url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
data = {
    "model": "gemini-1.5-flash",
    "messages": [{"role": "user", "content": "hi"}]
}
resp = requests.post(url, headers=headers, json=data)
print(f"Google OpenAI Compatible Endpoint: {resp.status_code}")
if resp.status_code == 200:
    print(resp.json())
else:
    print(resp.text)

