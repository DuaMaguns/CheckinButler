#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
doctor.py - environment self-check for the check-in toolkit.

Checks:
  1. Python version (>= 3.8 recommended)
  2. config/checkin_env.bat presence & required keys
  3. WorkBuddy credentials under scripts/workbuddy-checkin/auths/
     (file encoding, token expiry, disabled flag)
  4. Trae accounts (TRAE_ACCOUNTS JSON in config / config/trae-accounts/)
  5. Network reachability of the three API hosts
  6. Push channel (WeCom webhook / PushPlus) configured

Exit code 0 = no blocking problems, 1 = at least one blocking issue.
Run:  python doctor.py            (from anywhere)
      python doctor.py --json     (machine-readable output)
"""

import base64
import glob
import json
import os
import re
import socket
import subprocess
import sys
import time

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WB_DIR = os.path.join(TOOL_DIR, "scripts", "workbuddy-checkin")
TRAE_DIR = os.path.join(TOOL_DIR, "scripts", "Trae-AutoCheckin")
CFG_PATH = os.path.join(TOOL_DIR, "config", "checkin_env.bat")

HOSTS = [
    ("WorkBuddy API", "copilot.tencent.com", 443),
    ("Trae API", "api.trae.ai", 443),
]

REQUIRED_CFG_KEYS = ["QYWX_TOKEN"]          # at least one push channel
ALTERNATE_CFG_KEYS = ["QYWX_TOKEN", "PLUSPLUS_TOKEN"]

OK, WARN, FAIL, INFO = "[ OK ]", "[WARN]", "[FAIL]", "[ -- ]"
problems = []


def say(level, msg):
    print("%s %s" % (level, msg))


def check_python():
    v = sys.version_info
    if v >= (3, 8):
        say(OK, "Python %d.%d.%d" % v[:3])
    else:
        say(FAIL, "Python %d.%d too old, need >= 3.8" % v[:2])
        problems.append("python")


def check_config():
    if not os.path.isfile(CFG_PATH):
        say(FAIL, "config\\checkin_env.bat not found. Run setup.bat first, "
                  "or copy checkin_env.example.bat -> checkin_env.bat and fill it.")
        problems.append("config")
        return {}
    say(OK, "config\\checkin_env.bat found")
    cfg = {}
    pat = re.compile(r'^\s*set\s+"?([A-Za-z_][A-Za-z0-9_]*)=(.*)"?$', re.M)
    try:
        raw = open(CFG_PATH, encoding="utf-8", errors="replace").read()
    except OSError as e:
        say(FAIL, "cannot read config: %s" % e)
        problems.append("config")
        return cfg
    # strip value for display, keep key names
    for k, v in pat.findall(raw):
        v = v.strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        cfg[k] = v
    if not any(cfg.get(k) for k in ALTERNATE_CFG_KEYS):
        say(WARN, "no push channel configured (QYWX_TOKEN or PLUSPLUS_TOKEN) - "
                  "check-in will run but no notification is sent")
    else:
        say(OK, "push channel configured (%s)" %
            "/".join(k for k in ALTERNATE_CFG_KEYS if cfg.get(k)))
    if cfg.get("TRAE_ACCOUNTS"):
        say(OK, "TRAE_ACCOUNTS configured in config file")
    else:
        say(WARN, "TRAE_ACCOUNTS empty - Trae check-in will be skipped "
                  "(run get_tokens.bat / trae_add.bat to add)")
    return cfg


def jwt_exp(token):
    """best-effort: read 'exp' from a JWT access token"""
    try:
        pl = token.split(".")[1]
        pl += "=" * (-len(pl) % 4)
        d = json.loads(base64.b64decode(pl))
        d = d.get("data", d)
        return d.get("exp")
    except Exception:
        return None


def check_workbuddy():
    auth_dir = os.path.join(WB_DIR, "auths")
    files = [p for p in sorted(glob.glob(os.path.join(auth_dir, "*.json")))
             if not os.path.basename(p).startswith("auth.example")]
    if not files:
        say(FAIL, "no WorkBuddy credentials in scripts\\workbuddy-checkin\\auths\\ "
                  "(run wb_login.bat to add one)")
        problems.append("wb-cred")
        return
    say(INFO, "WorkBuddy credential files: %d" % len(files))
    for p in files:
        name = os.path.basename(p)
        try:
            raw = open(p, "rb").read()
            raw.decode("utf-8")
        except UnicodeDecodeError:
            say(FAIL, "%s: NOT valid UTF-8 (probably GBK) - the check-in "
                      "script will silently skip it. Re-save as UTF-8 or "
                      "re-run wb_login.bat" % name)
            problems.append("wb-enc")
            continue
        except OSError as e:
            say(FAIL, "%s: unreadable (%s)" % (name, e))
            problems.append("wb-cred")
            continue
        try:
            d = json.loads(raw.decode("utf-8"))
        except Exception as e:
            say(FAIL, "%s: broken JSON (%s)" % (name, e))
            problems.append("wb-json")
            continue
        if d.get("disabled"):
            say(WARN, "%s: disabled=true, will be skipped" % name)
            continue
        at = (d.get("auth") or {}).get("accessToken") or ""
        exp = jwt_exp(at)
        if exp:
            days = (exp - time.time()) / 86400
            if days < 0:
                say(FAIL, "%s: access token EXPIRED %.1f days ago "
                          "(refreshToken may still work; verify via 'credit')"
                    % (name, -days))
                problems.append("wb-exp")
            else:
                say(OK, "%s: token valid, %.1f days left" % (name, days))
        else:
            say(WARN, "%s: cannot read token expiry (format changed?) "
                      "- verify via workbuddy_checkin.py credit" % name)


def check_trae():
    cfg = check_trae.cfg
    n = 0
    if cfg.get("TRAE_ACCOUNTS"):
        try:
            arr = json.loads(cfg["TRAE_ACCOUNTS"])
            n = len(arr)
            say(OK, "Trae accounts in config: %d" % n)
        except Exception:
            say(FAIL, "TRAE_ACCOUNTS is not valid JSON - Trae check-in will fail")
            problems.append("trae-json")
    files = [p for p in glob.glob(os.path.join(TOOL_DIR, "config",
                                               "trae-accounts", "*.json"))]
    if files:
        say(INFO, "trae-accounts archive files: %d" % len(files))
    if n == 0 and not files:
        say(WARN, "no Trae account found anywhere - Trae check-in will be "
                  "skipped (run get_tokens.bat or trae_add.bat)")
    state = os.path.join(TRAE_DIR, ".trae_checkin_state.json")
    if os.path.isfile(state):
        say(INFO, "Trae daily state file present (today's results cached)")


def check_qoder():
    acc_path = os.path.join(TOOL_DIR, "scripts", "Qoder-Checkin", "accounts.json")
    cfg_path = os.path.join(TOOL_DIR, "scripts", "Qoder-Checkin", "config.json")
    if not os.path.isfile(acc_path):
        say(WARN, "no Qoder accounts (scripts\\Qoder-Checkin\\accounts.json missing) "
                  "- Qoder check-in is skipped (run qoder_add.bat to add)")
        return
    try:
        raw = open(acc_path, "rb").read()
        raw.decode("utf-8")
        d = json.loads(raw.decode("utf-8"))
    except Exception as e:
        say(FAIL, "Qoder accounts.json unreadable / not UTF-8: %s" % e)
        problems.append("qd-enc")
        return
    accs = d.get("accounts", [])
    n_ok = len([a for a in accs if a.get("accessToken") or a.get("refreshToken")])
    say(INFO, "Qoder accounts with tokens: %d/%d" % (n_ok, len(accs)))
    if not accs:
        say(WARN, "Qoder accounts.json is empty - run qoder_add.bat")
    if not os.path.isfile(cfg_path):
        say(FAIL, "Qoder config.json missing (device id block required)")
        problems.append("qd-cfg")
    else:
        try:
            c = json.load(open(cfg_path, encoding="utf-8"))
            dev = c.get("device") or {}
            if dev.get("machineToken") or dev.get("machineId"):
                say(OK, "Qoder device id present")
            else:
                say(FAIL, "Qoder device id empty - re-run qoder_add.bat "
                          "(stale device id causes endless 'pending')")
                problems.append("qd-dev")
        except Exception as e:
            say(FAIL, "Qoder config.json broken: %s" % e)
            problems.append("qd-cfg")


def check_network():
    for label, host, port in HOSTS:
        try:
            socket.create_connection((host, port), timeout=6).close()
            say(OK, "network: %s (%s:%d) reachable" % (label, host, port))
        except OSError as e:
            say(FAIL, "network: %s (%s:%d) UNREACHABLE: %s" % (label, host, port, e))
            problems.append("net-" + host)


def check_scripts():
    for py in (os.path.join(WB_DIR, "workbuddy_checkin.py"),
               os.path.join(TRAE_DIR, "trae_checkin.py"),
               os.path.join(TOOL_DIR, "scripts", "run_all.py")):
        r = subprocess.run([sys.executable, "-m", "py_compile", py],
                           capture_output=True)
        if r.returncode == 0:
            say(OK, "script OK: %s" % os.path.basename(py))
        else:
            say(FAIL, "script BROKEN: %s\n%s" % (py, r.stderr.decode(errors="replace")[:300]))
            problems.append("py:" + os.path.basename(py))


def summary():
    print()
    if problems:
        print("=" * 56)
        print("RESULT: %d blocking issue(s): %s" % (len(problems), ", ".join(problems)))
        print("Fix the [FAIL] items above, then run doctor.py again.")
        print("=" * 56)
        return 1
    print("=" * 56)
    print("RESULT: environment looks good. Next steps:")
    print("  1) wb_login.bat    - add WorkBuddy account(s)")
    print("  2) get_tokens.bat  - add Trae account(s)")
    print("  3) run_checkin.bat - first run + push test")
    print("=" * 56)
    return 0


def main():
    if "--json" in sys.argv:
        # simple machine-readable mode: problems list only
        check_python()
        cfg = check_config()
        check_trae.cfg = cfg
        check_workbuddy()
        check_trae()
        check_qoder()
        check_network()
        check_scripts()
        print(json.dumps({"problems": problems}, ensure_ascii=False))
        return 1 if problems else 0

    print("=" * 56)
    print("doctor.py - check-in toolkit self-check")
    print("Tool dir: %s" % TOOL_DIR)
    print("=" * 56)
    check_python()
    cfg = check_config()
    check_trae.cfg = cfg
    print()
    check_workbuddy()
    print()
    check_trae()
    print()
    check_qoder()
    print()
    check_network()
    print()
    check_scripts()
    return summary()


if __name__ == "__main__":
    sys.exit(main())
