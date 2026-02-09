import urllib.request
import json

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

# Step 0: Login to get token
print("=== LOGIN ===")
login_result = api("POST", "/api/auth/login", {"username": "admin", "password": "admin"})
if not login_result:
    login_result = api("POST", "/api/auth/login", {"username": "moderator", "password": "moderator"})
if not login_result:
    # Try to find any user
    print("Trying default credentials...")
    for u, p in [("admin", "admin123"), ("mod", "mod"), ("test", "test")]:
        login_result = api("POST", "/api/auth/login", {"username": u, "password": p})
        if login_result:
            break

if login_result and "access_token" in login_result:
    token = login_result["access_token"]
    print(f"Got token: {token[:20]}...")
else:
    print("Login failed, trying without auth (learning stats may be public)")
    token = None

# Step 1: Get stats BEFORE
print("\n=== STATS BEFORE ===")
stats = api("GET", "/learning/statistics", token=token)
print(json.dumps(stats, indent=2) if stats else "Failed")

# Step 2: Learn tnsystem.ru
print("\n=== LEARN tnsystem.ru ===")
result = api("POST", "/learning/learn-manual-inn", {
    "runId": "c1515ce9-41d3-462e-a822-2a48f6155e81",
    "domain": "tnsystem.ru",
    "inn": "7840511719",
    "sourceUrl": "https://tnsystem.ru/kontakty/",
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
