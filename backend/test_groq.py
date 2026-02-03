import httpx
import json
import os

def test_groq_key(api_key: str) -> dict:
    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = {
        "model": "llama-3.1-8b-instant",
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant. Respond with a simple test message."},
            {"role": "user", "content": "Say 'Groq test successful'"}
        ]
    }
    headers = {"Authorization": f"Bearer {api_key}"}

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            usage = data.get("usage", {})
            return {"success": True, "content": content, "usage": usage}
    except httpx.HTTPStatusError as e:
        return {"success": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    key = os.getenv("GROQ_API_KEY")
    if not key:
        print("Ошибка: GROQ_API_KEY не найден в переменных окружения")
        exit(1)
    result = test_groq_key(key)
    print(json.dumps(result, ensure_ascii=False, indent=2))
