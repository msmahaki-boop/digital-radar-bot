
import os
import json
import urllib.request
import urllib.error

API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL = "gemini-3.1-flash-lite"

if not API_KEY:
    raise SystemExit("GEMINI_API_KEY is missing.")

url = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{MODEL}:generateContent"
)

payload = {
    "contents": [
        {
            "parts": [
                {
                    "text": (
                        "Translate this technology news headline "
                        "into natural Persian. Reply with only "
                        "the Persian translation:\n"
                        "Instagram launches new tools for creators"
                    )
                }
            ]
        }
    ],
    "generationConfig": {
        "temperature": 0.1,
        "maxOutputTokens": 1024
    }
}

request = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={
        "x-goog-api-key": API_KEY,
        "Content-Type": "application/json"
    },
    method="POST"
)

try:
    with urllib.request.urlopen(
        request, timeout=60
    ) as response:
        result = json.load(response)

except urllib.error.HTTPError as error:
    try:
        details = json.loads(error.read())
        message = details.get("error", {}).get(
            "message", "Unknown API error"
        )
    except Exception:
        message = "API request was rejected."

    message = message.replace(API_KEY, "[HIDDEN]")
    raise SystemExit(
        f"Gemini API error {error.code}: {message[:300]}"
    ) from None

except urllib.error.URLError:
    raise SystemExit(
        "Cannot connect to Gemini API."
    ) from None

try:
    parts = result["candidates"][0]["content"]["parts"]
    answer = " ".join(
        part.get("text", "")
        for part in parts
    ).strip()

    if not answer:
        raise ValueError("Empty response")

except (KeyError, IndexError, ValueError):
    raise SystemExit(
        "Gemini returned no usable text."
    ) from None

print("SUCCESS: Gemini connection established!")
print("Model:", MODEL)
print("Persian translation:", answer)
