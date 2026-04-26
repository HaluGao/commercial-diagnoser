import requests
# Using a public generic curl to an invalid key to see if 404 or 400 is returned
for m in ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-1.5-flash-001", "gemini-1.5-flash-002"]:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key=FAKE_KEY"
    payload = {"contents": [{"role": "user", "parts": [{"text": "1"}]}]}
    r = requests.post(url, json=payload)
    print(f"{m} -> {r.status_code} {r.text[:100]}")
