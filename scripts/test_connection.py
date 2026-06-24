"""
Jira Cloud REST API Connection Test
Site: ftdr-sandbox-438.atlassian.net
Auth: Basic (email + API token via FTDR_CLOUD_PAT)
"""

import os
import sys
import json
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from base64 import b64encode

SITE = "https://ftdr-sandbox-438.atlassian.net"
EMAIL = "jax.kane@frontdoor.com"
PAT = os.environ.get("FTDR_CLOUD_PAT")

if not PAT:
    print("ERROR: Set FTDR_CLOUD_PAT environment variable first.")
    print("  export FTDR_CLOUD_PAT='your-api-token'")
    sys.exit(1)

credentials = b64encode(f"{EMAIL}:{PAT}".encode()).decode()
headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json",
}


def api_get(endpoint):
    url = f"{SITE}{endpoint}"
    req = Request(url, headers=headers)
    try:
        with urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as e:
        return e.code, {"error": e.reason}
    except URLError as e:
        return 0, {"error": str(e.reason)}


def main():
    print("=" * 60)
    print("  Jira Cloud REST API Connection Test")
    print(f"  Site: {SITE}")
    print(f"  User: {EMAIL}")
    print("=" * 60)
    print()

    # Test 1: Authentication
    print("[1] Testing authentication (/rest/api/3/myself)...")
    status, data = api_get("/rest/api/3/myself")
    if status == 200:
        print(f"    ✅ Authenticated as: {data['displayName']}")
        print(f"    Account ID: {data['accountId']}")
        print(f"    Email: {data.get('emailAddress', 'N/A')}")
        print(f"    Time Zone: {data.get('timeZone', 'N/A')}")
        print(f"    Active: {data.get('active', 'N/A')}")
    else:
        print(f"    ❌ Auth failed (HTTP {status}): {data}")
        sys.exit(1)
    print()

    # Test 2: Project access
    print("[2] Testing project access (/rest/api/3/project/search)...")
    status, data = api_get("/rest/api/3/project/search?maxResults=5")
    if status == 200:
        total = data.get("total", 0)
        print(f"    ✅ Can read projects: {total} total")
        for p in data.get("values", [])[:5]:
            print(f"    - {p['key']}: {p['name']} ({p.get('projectTypeKey', '?')})")
    else:
        print(f"    ❌ Failed (HTTP {status}): {data}")
    print()

    # Test 3: Issue search (JQL) — try v2 first, fall back to v3
    print("[3] Testing JQL search...")
    status, data = api_get("/rest/api/3/search/jql?jql=updated+%3E%3D+-30d+ORDER+BY+updated+DESC&maxResults=3&fields=key,summary,status")
    if status == 200:
        total = data.get("total", 0)
        print(f"    ✅ Can search issues (v2 endpoint): {total} total")
        for issue in data.get("issues", [])[:3]:
            key = issue["key"]
            summary = issue["fields"]["summary"][:60]
            status_name = issue["fields"]["status"]["name"]
            print(f"    - {key}: {summary} [{status_name}]")
    else:
        # Fall back to legacy endpoint
        status2, data2 = api_get("/rest/api/3/search?jql=ORDER+BY+updated+DESC&maxResults=3&fields=key,summary,status")
        if status2 == 200:
            total = data2.get("total", 0)
            print(f"    ✅ Can search issues (legacy endpoint): {total} total")
            for issue in data2.get("issues", [])[:3]:
                key = issue["key"]
                summary = issue["fields"]["summary"][:60]
                status_name = issue["fields"]["status"]["name"]
                print(f"    - {key}: {summary} [{status_name}]")
        else:
            print(f"    ❌ Both endpoints failed: v2={status}, legacy={status2}")
    print()

    # Test 4: Permissions check
    print("[4] Testing permission access...")
    status, data = api_get("/rest/api/3/mypermissions?permissions=BROWSE_PROJECTS,CREATE_ISSUES,ADMINISTER")
    if status == 200:
        perms = data.get("permissions", {})
        for perm_name in ["BROWSE_PROJECTS", "CREATE_ISSUES", "ADMINISTER"]:
            perm = perms.get(perm_name, {})
            granted = "✅" if perm.get("havePermission") else "❌"
            print(f"    {granted} {perm_name}")
    else:
        print(f"    ❌ Failed (HTTP {status}): {data}")
    print()

    # Test 5: Agile/Board access
    print("[5] Testing Agile API (/rest/agile/1.0/board)...")
    status, data = api_get("/rest/agile/1.0/board?maxResults=3")
    if status == 200:
        total = data.get("total", 0)
        print(f"    ✅ Can read boards: {total} total")
        for b in data.get("values", [])[:3]:
            print(f"    - {b['name']} ({b.get('type', '?')})")
    else:
        print(f"    ❌ Failed (HTTP {status}): {data}")
    print()

    print("=" * 60)
    print("  CONNECTION TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
