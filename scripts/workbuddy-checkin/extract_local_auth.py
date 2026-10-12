#!/usr/bin/env python3
"""Extract WorkBuddy desktop login state -> auths/workbuddy-<uid>.json
Reads local auth file, never prints tokens. Windows/macOS/Linux.
"""
import base64
import json
import os
import sys
import time

CANDIDATE_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info"),
    os.path.expandvars(r"%APPDATA%\CodeBuddyExtension\Data\Public\auth\workbuddy-desktop.info"),
    os.path.expanduser("~/Library/Application Support/CodeBuddyExtension/Data/Public/auth/workbuddy-desktop.info"),
    os.path.expanduser("~/.codebuddy/workbuddy-desktop.info"),
]

AUTH_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "auths")


def load_info():
    for p in CANDIDATE_PATHS:
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8", errors="replace") as f:
                raw = f.read()
            try:
                return p, json.loads(raw)
            except json.JSONDecodeError:
                # file may contain multiple JSON objects or wrapper text
                print("  WARN: %s is not pure JSON, trying lenient parse" % p)
                dec = json.JSONDecoder()
                idx = raw.find("{")
                while idx != -1:
                    try:
                        obj, _ = dec.raw_decode(raw[idx:])
                        if isinstance(obj, dict):
                            return p, obj
                    except json.JSONDecodeError:
                        pass
                    idx = raw.find("{", idx + 1)
    return None, None


def parse_account(access_token):
    try:
        payload = access_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        d = json.loads(base64.b64decode(payload))
        data = d.get("data", d)
        return {
            "uid": str(data.get("uid") or data.get("sub") or ""),
            "enterpriseId": str(data.get("enterpriseId") or ""),
            "nickname": data.get("nickname") or data.get("name") or "Unknown",
        }
    except Exception:
        return {"uid": "", "enterpriseId": "", "nickname": "Unknown"}


def main():
    path, info = load_info()
    if not info:
        print("FAIL: no WorkBuddy desktop auth file found. Is the client installed & logged in?")
        sys.exit(1)
    print("Found auth file:", path)

    auth = info.get("auth", info)
    access_token = auth.get("accessToken") or auth.get("access_token") or ""
    refresh_token = auth.get("refreshToken") or auth.get("refresh_token") or ""
    expires_at = auth.get("expiresAt") or auth.get("expires_at") or 0
    domain = auth.get("domain") or "www.codebuddy.cn"

    if not access_token:
        print("FAIL: no accessToken inside auth file")
        sys.exit(1)

    account = info.get("account") or {}
    if not account.get("uid"):
        account = parse_account(access_token)
    uid = account.get("uid") or "unknown"
    print("Account:", account.get("nickname"), "| uid:", uid)
    if refresh_token:
        print("refreshToken: present")
    else:
        print("refreshToken: MISSING (token will not auto-renew; re-extract after expiry)")
    days = 0
    if isinstance(expires_at, (int, float)) and expires_at > 10**9:
        days = (expires_at - time.time()) / 86400
        print("token expires in: %.1f days" % max(days, 0))
    if days and days < 1:
        print("WARN: token expires within 24h — reopen WorkBuddy client to refresh, then re-run this script")

    os.makedirs(AUTH_DIR, exist_ok=True)
    cred = {
        "auth": {
            "accessToken": access_token,
            "refreshToken": refresh_token,
            "expiresAt": expires_at if isinstance(expires_at, (int, float)) else 0,
            "domain": domain,
        },
        "account": account,
        "disabled": False,
    }
    out = os.path.join(AUTH_DIR, "workbuddy-%s.json" % uid)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cred, f, indent=2, ensure_ascii=False)
    print("OK, credential saved:", out)
    print("Accounts in auths/:", len([f for f in os.listdir(AUTH_DIR) if f.startswith("workbuddy-") and f.endswith(".json")]))


if __name__ == "__main__":
    main()
