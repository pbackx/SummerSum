import os

api_key = os.environ.get("GEMINI_API_KEY")
if api_key:
    print(f"GEMINI_API_KEY is set. Length: {len(api_key)}. Starts with: {api_key[:4]}")
else:
    print("GEMINI_API_KEY is NOT set.")
