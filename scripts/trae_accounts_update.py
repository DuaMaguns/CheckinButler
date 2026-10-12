#!/usr/bin/env python3
"""trae_accounts_update.py - archive the currently logged-in Trae client
account into the account dir, then regenerate TRAE_ACCOUNTS in config.

Workflow for adding accounts:
  1. In Trae client, log in with the account you want to add
  2. Run this script (or trae_add.bat)
  3. It archives that account as trae-<uid>.json, merges ALL archived
     accounts with the current client login state, and rewrites the
     TRAE_ACCOUNTS line in config\\checkin_env.bat
Repeat step 1-2 for each additional account.
"""
import io
import json
import os
import re
import subprocess
import sys

# 根目录 = 本文件所在目录(scripts)的上一级，项目可整体搬家 / 改名。
TOOL_DIR = os.environ.get("CHECKIN_TOOL_DIR", "").strip() or \
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAE_DIR = os.path.join(TOOL_DIR, "scripts", "Trae-AutoCheckin")
CONFIG = os.path.join(TOOL_DIR, "config", "checkin_env.bat")
ACCOUNT_DIR = os.path.join(TOOL_DIR, "config", "trae-accounts")
PY = sys.executable

sys.path.insert(0, TRAE_DIR)
import trae_get_token as tgt  # noqa: E402


def archive_current_login():
    """Save the currently logged-in client account as trae-<uid>.json."""
    os.makedirs(ACCOUNT_DIR, exist_ok=True)
    saved = None
    for path in tgt.candidate_paths():
        if not os.path.exists(path):
            continue
        try:
            r = tgt.extract(path)
        except Exception as e:
            print("[!] parse failed %s: %s" % (path, e))
            continue
        if r and r.get("refreshToken"):
            saved = (path, r)
            break
    if not saved:
        print("[X] No logged-in Trae client account found on this machine.")
        print("    Log in to the Trae client first, then re-run.")
        return None
    path, r = saved
    uid = r.get("uid") or ("u" + abs(hash(r["refreshToken"])) % 10**10).__str__()
    nick = r.get("nickname") or uid
    rec = {
        "auth": {"accessToken": r.get("accessToken") or "", "refreshToken": r["refreshToken"]},
        "account": {"uid": uid, "nickname": nick},
    }
    out = os.path.join(ACCOUNT_DIR, "trae-%s.json" % uid)
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, indent=2)
    print("[OK] Archived current client login: %s (%s)" % (nick, uid))
    print("     -> %s" % out)
    return uid


def regenerate_accounts_line():
    """Run --accounts with ACCOUNT_DIR and rewrite the TRAE_ACCOUNTS line."""
    env = os.environ.copy()
    env["TRAE_ACCOUNT_DIR"] = ACCOUNT_DIR
    r = subprocess.run([PY, os.path.join(TRAE_DIR, "trae_get_token.py"), "--accounts"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env=env, cwd=TRAE_DIR)
    m = re.search(r"(\[\{.*\}\])", r.stdout, re.S)
    if not m:
        print("[X] Failed to generate TRAE_ACCOUNTS:")
        print(r.stdout[-500:], r.stderr[-300:])
        return False
    line = m.group(1).strip()
    accounts = json.loads(line)
    print("[OK] TRAE_ACCOUNTS now has %d account(s):" % len(accounts))
    for i, a in enumerate(accounts, 1):
        print("   %d) %s  (uid %s)" % (i, a.get("name") or "-", a.get("uid") or "-"))

    # rewrite ONLY the TRAE_ACCOUNTS line (line-based, no greedy regex)
    with io.open(CONFIG, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    hit = False
    for i, ln in enumerate(lines):
        if ln.startswith('set "TRAE_ACCOUNTS='):
            lines[i] = 'set "TRAE_ACCOUNTS=%s"\n' % line
            hit = True
            break
    if not hit:
        lines.append('set "TRAE_ACCOUNTS=%s"\n' % line)
    with io.open(CONFIG, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print("[OK] config\\checkin_env.bat updated")
    return True


if __name__ == "__main__":
    archive_current_login()
    regenerate_accounts_line()
