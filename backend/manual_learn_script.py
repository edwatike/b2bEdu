from app.utils.auth import create_access_token
import json
import urllib.request
from datetime import timedelta

# Generate a valid token locally
token = create_access_token({"sub": "admin", "role": "admin"}, expires_delta=timedelta(days=1))
print(f"Generated token: {token}")

base = "http://localhost:8000"

def api(method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(f"{base}{path}", data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req)
        return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        print(f"ERROR {e.code}: {err}")
        return None

# Step 1: Get stats BEFORE
print("\n=== STATS BEFORE ===")
stats = api("GET", "/learning/statistics", token=token)
print(json.dumps(stats, indent=2) if stats else "Failed")

# Step 2: Learn tn.ru
print("\n=== LEARN tn.ru ===")
result = api("POST", "/learning/learn-manual-inn", {
    "runId": "c1515ce9-41d3-462e-a822-2a48f6155e81",
    "domain": "tn.ru",
    "inn": "7702521529",
    "sourceUrl": "https://shop.tn.ru/contact",
    "learningSessionId": "manual-2026-02-09"
}, token=token)
print(json.dumps(result, indent=2) if result else "Failed")

# Step 2.5: Learn tophouse.ru
print("\n=== LEARN tophouse.ru ===")
result = api("POST", "/learning/learn-manual-inn", {
    "runId": "c1515ce9-41d3-462e-a822-2a48f6155e81",
    "domain": "tophouse.ru",
    "inn": "7825352133",
    "sourceUrl": "https://tophouse.ru/company/rekvizit.php",
    "learningSessionId": "manual-2026-02-09"
}, token=token)
print(json.dumps(result, indent=2) if result else "Failed")

# Step 3: Get stats AFTER
print("\n=== STATS AFTER ===")
stats_after = api("GET", "/learning/statistics", token=token)
print(json.dumps(stats_after, indent=2) if stats_after else "Failed")

# Step 4: Learned summary
print("\n=== LEARNED SUMMARY ===")
summary = api("GET", "/learning/learned-summary?limit=30", token=token)
print(json.dumps(summary, indent=2) if summary else "Failed")
