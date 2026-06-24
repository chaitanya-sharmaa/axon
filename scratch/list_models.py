import requests
key = "REDACTED_API_KEY"
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
resp = requests.get(url)
print(resp.status_code)
if resp.status_code == 200:
    for m in resp.json().get("models", []):
        print(m["name"])
else:
    print(resp.text)
