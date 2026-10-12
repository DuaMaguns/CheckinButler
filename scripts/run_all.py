#!/usr/bin/env python3
"""run_all.py - unified scheduler for the check-in tool.

Flow:
  1. Load config from config\\checkin_env.bat (set "KEY=VALUE" lines)
  2. Run Trae multi-account check-in   (native push disabled)
  3. Run WorkBuddy multi-account API check-in
  4. Run Qoder multi-account check-in  (native push disabled)
  5. Send ONE combined WeCom/PushPlus markdown summary
  6. Append everything to logs\\checkin_YYYY-MM-DD.log
"""
import base64
import datetime
import glob
import io
import json
import os
import re
import subprocess
import sys
import urllib.request

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAE_DIR = os.path.join(TOOL_DIR, "scripts", "Trae-AutoCheckin")
WB_DIR = os.path.join(TOOL_DIR, "scripts", "workbuddy-checkin")
WB_AUTHS = os.path.join(WB_DIR, "auths")
QODER_DIR = os.path.join(TOOL_DIR, "scripts", "Qoder-Checkin")
QODER_ACCOUNTS = os.path.join(QODER_DIR, "accounts.json")
LOG_DIR = os.path.join(TOOL_DIR, "logs")
CONFIG = os.path.join(TOOL_DIR, "config", "checkin_env.bat")
# 当日完成标记：签到全部完成并推送过一次后，重复执行直接跳过，避免反复推送
STATE_PATH = os.path.join(TOOL_DIR, "scripts", ".checkin_state.json")

WECOM_BASE = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
PUSHPLUS_BASE = "https://www.pushplus.plus/send"


def load_config():
    cfg = {}
    try:
        with open(CONFIG, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r'set "([A-Za-z_][A-Za-z0-9_]*)=(.*)"\s*$', line.strip())
                if m:
                    cfg[m.group(1)] = m.group(2)
    except OSError:
        pass
    return cfg


def trae_account_names():
    """Trae 账号显示名列表（用于判断账号集合是否变化）。"""
    names = []
    for d in (os.path.join(TRAE_DIR, "config", "trae-accounts"),
              os.path.join(TOOL_DIR, "config", "trae-accounts")):
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            try:
                d = json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            acc = d.get("account") or {}
            n = ((acc.get("nickname") or d.get("name") or "").strip()
                 or os.path.basename(p)[5:-5])
            if n not in names:
                names.append(n)
    return names


def qoder_account_names():
    """Qoder 账号显示名列表（用于判断账号集合是否变化）。"""
    names = []
    try:
        d = json.load(open(QODER_ACCOUNTS, encoding="utf-8"))
    except Exception:
        return names
    for i, acc in enumerate(d.get("accounts", [])):
        n = (acc.get("name") or acc.get("uid") or ("Qoder-%d" % (i + 1)))
        if n not in names:
            names.append(n)
    return names


def load_state():
    try:
        with io.open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    try:
        with io.open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("WARN: cannot write state file: %s" % e)


def log(msg, logf=None):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line, flush=True)
    if logf:
        logf.write(line + "\n")
        logf.flush()


def run_step(name, cwd, args, extra_env, logf=None):
    log("Running %s ..." % name, logf)
    env = os.environ.copy()
    env.update(extra_env)
    # force UTF-8 stdio: Task Scheduler/cmd env uses GBK, emoji output crashes
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    # disable Trae's built-in push: summary is sent once, combined
    env.pop("QYWX_TOKEN", None)
    env.pop("PLUSPLUS_TOKEN", None)
    env.pop("WECHAT_WEBHOOK", None)
    try:
        r = subprocess.run(
            [sys.executable] + args,
            cwd=cwd, env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        out = (r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else "")
        log("%s exit code: %s" % (name, r.returncode), logf)
        return r.returncode, out
    except Exception as e:
        log("%s FAILED to run: %s" % (name, e), logf)
        return 1, str(e)


# ---------------------------------------------------------------- parsing

def parse_trae_accounts(out):
    """Per-account status from trae_checkin.py output."""
    results = []
    seen = {}
    current = None

    def set_status(name, status, note=""):
        rec = seen.get(name)
        if rec is None:
            rec = {"name": name, "status": "", "note": ""}
            seen[name] = rec
            results.append(rec)
        # priority: fail > retry > success > already
        rank = {"fail": 0, "retry": 1, "success": 2, "already": 3}
        if rec["status"] == "" or rank.get(status, 9) < rank.get(rec["status"], 9):
            rec["status"] = status
        if note:
            rec["note"] = note

    for ln in out.splitlines():
        m = re.search("\U0001F4E1\\s*(.+?)\\s+\u7b7e\u5230\u72b6\u6001\u67e5\u8be2", ln)
        if m:
            current = m.group(1).strip()
            continue
        m = re.search("\u2611\\ufe0f?\\s*\\[(.+?)\\]", ln)
        if m:
            who = m.group(1).strip()
            # “☑️ [结果] …” 是流程日志，不是账号名
            if who not in ("\u7ed3\u679c",):
                set_status(who, "already")
                current = who
            continue
        # Trae 的积分/到期明细行（紧跟在该账号的状态行之后）
        mc = re.search(
            "\u5269\u4f59\u79ef\u5206:\\s*([\\d,\\.]+).*?"
            "\u6700\u8fd1\u5230\u671f:\\s*([\\d\\-]+ ?[\\d:]*)\\s*\\((\\d+)\\s*\u5929\u540e\\)\\s*\\|\\s*"
            "\u5230\u671f\u79ef\u5206:\\s*([\\d,\\.]+)", ln)
        if mc and current:
            set_status(current, "already", "\u5269\u4f59%s \u00b7 %s\u5230\u671f%s(%s\u5929)" % (
                mc.group(1), mc.group(2)[5:], mc.group(4), mc.group(3)))
            continue
        if "\U0001F389" in ln and "\u7b7e\u5230\u6210\u529f" in ln and current:
            set_status(current, "success")
            continue
        if "9074" in ln:
            # cooldown lines carry the account name inline: ⏳ [冷却] <name> 9074 ...
            mc = re.search("\u51b7\u5374\\]\\s*(\\S+)", ln)
            who = mc.group(1) if mc else current
            if who:
                set_status(who, "retry", "9074")
            continue
        if ("\u5f85\u91cd\u8bd5" in ln and current
                and "\u2551" not in ln and "\u2550" not in ln):
            set_status(current, "retry", "9074")
            continue
        if ("\u5931\u8d25" in ln and current and "\u5931\u8d25 0" not in ln
                and "exit code" not in ln):
            if re.search("\u274c|\u7b7e\u5230\u5931\u8d25|\u9274\u6743\u5931\u8d25", ln):
                set_status(current, "fail")
    return results


QODER_PHASE = {
    "\u7b7e\u5230\u6210\u529f": "success",   # ✅ 签到成功
    "\u5df2\u9886\u53d6": "already",          # ☑️ 已领取
    "\u5f85\u4e0b\u53d1": "retry",            # ⏳ 待下发
    "\u9700\u91cd\u65b0\u767b\u5f55": "fail",  # 🔑 需重新登录
    "\u5931\u8d25": "fail",                   # ❌ 失败
}


def parse_qoder_accounts(out):
    """Per-account status from 02_checkin.py output.

    Line format: "  ✅ 签到成功 账号1: 签到成功 +100 Credits（+100）"
    """
    results = []
    pat = re.compile(
        "^\\s*(?:\u2705|\u2611\\ufe0f?|\u23f3|\U0001F511|\u274c)\\s*"
        "(\u7b7e\u5230\u6210\u529f|\u5df2\u9886\u53d6|\u5f85\u4e0b\u53d1|\u9700\u91cd\u65b0\u767b\u5f55|\u5931\u8d25)"
        "\\s+(.+?):\\s*(.*)$")
    for ln in out.splitlines():
        m = pat.match(ln)
        if not m:
            continue
        phase, name, msg = m.group(1), m.group(2).strip(), m.group(3).strip()
        status = QODER_PHASE.get(phase, "")
        note = msg[:60]
        results.append({"name": name, "status": status, "note": note})
    return results


def wb_name_map():
    """uid -> display name from auths files (token preferred_username as fallback)."""
    mapping = {}
    for p in glob.glob(os.path.join(WB_AUTHS, "workbuddy-*.json")):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        acc = d.get("account") or {}
        uid = acc.get("uid") or ""
        nick = (acc.get("nickname") or "").strip()
        if not nick or nick == uid:
            at = (d.get("auth") or {}).get("accessToken") or ""
            try:
                payload = at.split(".")[1]
                payload += "=" * (-len(payload) % 4)
                dd = json.loads(base64.b64decode(payload))
                dd = dd.get("data", dd)
                nick = dd.get("preferred_username") or ""
            except Exception:
                nick = ""
        mapping[uid] = nick or ("WB-" + uid[:8])
    return mapping


def parse_wb_accounts(out, name_map):
    """Per-account status from workbuddy_checkin.py output."""
    results = []
    lines = out.splitlines()
    for i, ln in enumerate(lines):
        m = re.search(r"\[(CN|Global)\]\s*(.*?)\(?([\w-]{20,})\)?\s*[:\uff1a]\s*(.*)", ln)
        if not m:
            continue
        region, nick, uid, rest = m.group(1), m.group(2).strip(), m.group(3), m.group(4).strip()
        name = name_map.get(uid) or nick or ("WB-" + uid[:8])
        note = rest[:60]
        if re.search("\u5df2\u7b7e|already", rest):
            status = "already"
        elif re.search("\u6210\u529f|OK", rest) and not re.search("\u5931\u8d25", rest):
            status = "success"
        elif re.search("disabled|12153|\u5931\u6548", rest):
            status = "fail"
        else:
            status = "retry"
        # 紧随其后的 3 行里抓：连签天数，以及 剩余积分/最近到期/到期积分
        bits = []
        for j in range(i + 1, min(i + 4, len(lines))):
            ln2 = lines[j]
            sm = re.search("\u8fde\u7b7e:\\s*(\\d+)\\s*\u5929", ln2)
            if sm and not bits:
                bits.append("\u8fde\u7b7e%s\u5929" % sm.group(1))
            cm = re.search(
                "\u5269\u4f59\u79ef\u5206:\\s*(\\d+).*?"
                "\u6700\u8fd1\u5230\u671f:\\s*([\\d\\-]+ ?[\\d:]*)\\s*\\((\\d+)\\s*\u5929\u540e\\)\\s*\\|\\s*"
                "\u5230\u671f\u79ef\u5206:\\s*(\\d+)", ln2)
            if cm:
                bits.append("\u5269\u4f59%s \u00b7 %s\u5230\u671f%s(%s\u5929)" % (
                    cm.group(1), cm.group(2)[5:], cm.group(4), cm.group(3)))
                break
        if bits:
            note = " \u00b7 ".join(bits)

        results.append({"name": name, "status": status, "note": note})
    return results


# ---------------------------------------------------------------- message

STATUS_MARK = {
    "success": ("\u2705", "info"),
    "already": ("\u2705", "info"),
    "retry": ("\u23f3", "warning"),
    "fail": ("\u274c", "warning"),
    "": ("\u2753", "comment"),
}


def build_message(today, trae_accs, wb_accs, qoder_accs, trae_code, wb_code, qoder_code):
    def line_for(rec):
        mark, color = STATUS_MARK.get(rec["status"], STATUS_MARK[""])
        txt = "%s %s" % (mark, rec["name"])
        if rec["status"] == "already":
            txt += " \u00b7 \u4eca\u65e5\u5df2\u7b7e"
        elif rec["status"] == "success":
            txt += " \u00b7 \u7b7e\u5230\u6210\u529f"
        elif rec["status"] == "retry":
            txt += " \u00b7 \u98ce\u63a7\u5f85\u91cd\u8bd5(9074)"
        elif rec["status"] == "fail":
            txt += " \u00b7 \u5931\u8d25"
        if rec["note"]:
            txt += " \u00b7 " + rec["note"]
        return '> <font color="%s">%s</font>' % (color, txt)

    parts = ["**\U0001F4CB \u6bcf\u65e5\u7b7e\u5230\u62a5\u544a**",
             '<font color="comment">%s %s</font>' % (
                 today, datetime.datetime.now().strftime("%H:%M")), ""]

    parts.append("**Trae**\uff08%d \u4e2a\u8d26\u53f7\uff09" % max(len(trae_accs), 1))
    if trae_accs:
        parts += [line_for(a) for a in trae_accs]
    else:
        parts.append('> <font color="warning">\u672a\u83b7\u53d6\u5230\u8d26\u53f7\u72b6\u6001</font>')

    parts.append("")
    parts.append("**WorkBuddy**\uff08%d \u4e2a\u8d26\u53f7\uff09" % max(len(wb_accs), 1))
    if wb_accs:
        parts += [line_for(a) for a in wb_accs]
    else:
        parts.append('> <font color="warning">\u672a\u83b7\u53d6\u5230\u8d26\u53f7\u72b6\u6001</font>')

    parts.append("")
    parts.append("**Qoder**\uff08%d \u4e2a\u8d26\u53f7\uff09" % max(len(qoder_accs), 1))
    if qoder_accs:
        parts += [line_for(a) for a in qoder_accs]
    else:
        parts.append('> <font color="warning">\u672a\u83b7\u53d6\u5230\u8d26\u53f7\u72b6\u6001</font>')

    all_recs = trae_accs + wb_accs + qoder_accs
    if all_recs:
        n_already = len([a for a in all_recs if a["status"] == "already"])
        n_success = len([a for a in all_recs if a["status"] == "success"])
        n_retry = len([a for a in all_recs if a["status"] == "retry"])
        n_fail = len([a for a in all_recs if a["status"] == "fail"])
        if n_fail:
            overall, oc = "\U0001F534 \u6709\u8d26\u53f7\u5931\u8d25\uff0c\u9700\u5173\u6ce8", "warning"
        elif n_retry:
            overall, oc = "\U0001F7E1 \u90e8\u5206\u8d26\u53f7\u7b49\u5f85\u8865\u7b7e", "warning"
        else:
            overall, oc = "\U0001F7E2 \u5168\u90e8\u8d26\u53f7\u5b8c\u6210", "info"
        summary = "%s \u00b7 \u6210\u529f%d \u5df2\u7b7e%d \u5f85\u91cd\u8bd5%d \u5931\u8d25%d" % (
            overall, n_success, n_already, n_retry, n_fail)
        parts.append("")
        parts.append('<font color="%s">%s</font>' % (oc, summary))
    if trae_code != 0 or wb_code != 0 or qoder_code != 0:
        parts.append('<font color="warning">\u26a0\ufe0f \u811a\u672c\u9000\u51fa\u7801\u5f02\u5e38 trae=%s wb=%s qoder=%s\uff0c\u8be6\u89c1\u65e5\u5fd7</font>' % (trae_code, wb_code, qoder_code))
    return "\n".join(parts)


# ---------------------------------------------------------------- push

def push_wecom(key, content):
    payload = {"msgtype": "markdown", "markdown": {"content": content[:4000]}}
    req = urllib.request.Request(
        WECOM_BASE + key,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode())
        return d.get("errcode") == 0, d


def push_pushplus(token, title, content):
    payload = {"token": token, "title": title, "content": content, "template": "txt"}
    req = urllib.request.Request(
        PUSHPLUS_BASE,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode())
        return d.get("code") == 200, d


# ---------------------------------------------------------------- main

def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    log_path = os.path.join(LOG_DIR, "checkin_%s.log" % datetime.date.today().isoformat())
    logf = io.open(log_path, "a", encoding="utf-8")

    cfg = load_config()
    today = datetime.date.today().isoformat()
    force = "--force" in sys.argv or "-f" in sys.argv

    log("=" * 44, logf)
    log("Check-in run started", logf)

    # --- Step 0: 当日已完成则直接跳过（不重复签到、不重复推送）---
    # 账号集合变了（比如中途新加了号）就不算已完成，照常执行
    state = load_state()
    current_names = (set(wb_name_map().values()) | set(trae_account_names())
                     | set(qoder_account_names()))
    if not force and state.get("completed_date") == today \
            and set(state.get("accounts", [])) == current_names:
        log("Skip: today's check-in already completed at %s "
            "(accounts: %s). Use --force to run anyway."
            % (state.get("completed_at", "?"),
               ", ".join(sorted(current_names)) or "-"), logf)
        logf.close()
        return

    # --- Step 1: Trae ---
    trae_env = {k: v for k, v in cfg.items() if k.startswith("TRAE_")}
    code_trae, out_trae = run_step("Trae check-in", TRAE_DIR, ["trae_checkin.py"], trae_env, logf)
    log("--- Trae output ---", logf)
    log(out_trae.strip() or "(no output)", logf)

    # --- Step 2: WorkBuddy ---
    code_wb, out_wb = run_step("WorkBuddy check-in", WB_DIR,
                               ["workbuddy_checkin.py", "signin"], {}, logf)
    log("--- WorkBuddy output ---", logf)
    log(out_wb.strip() or "(no output)", logf)

    # --- Step 2.5: Qoder（有凭证才跑，未配置时静默跳过）---
    if os.path.isfile(QODER_ACCOUNTS):
        code_qd, out_qd = run_step("Qoder check-in", QODER_DIR,
                                   ["02_checkin.py"], {}, logf)
        log("--- Qoder output ---", logf)
        log(out_qd.strip() or "(no output)", logf)
    else:
        code_qd, out_qd = 0, ""
        log("Qoder check-in: skipped (no accounts.json)", logf)

    # --- Step 3: build push message ---
    trae_accs = parse_trae_accounts(out_trae)
    wb_accs = parse_wb_accounts(out_wb, wb_name_map())
    qoder_accs = parse_qoder_accounts(out_qd)
    content = build_message(today, trae_accs, wb_accs, qoder_accs,
                            code_trae, code_wb, code_qd)
    log("--- Push message ---", logf)
    log(content, logf)

    # --- Step 4: 是否推送 ---
    all_recs = trae_accs + wb_accs + qoder_accs
    pending = [a for a in all_recs if a["status"] in ("retry", "fail", "")]
    if pending:
        should_push, reason = True, "%d 个账号未完成，推送跟踪" % len(pending)
    elif not all_recs:
        should_push, reason = True, "未解析到账号状态，推送告警"
    elif state.get("completed_date") == today and not force:
        should_push, reason = False, "今日已完成且已推送过，跳过"
    elif state.get("completed_date") == today and force:
        should_push, reason = True, "--force 强制执行，重复推送"
    else:
        should_push, reason = True, "今日首次全部完成，推送汇报"
    log("Push decision: %s — %s" % ("PUSH" if should_push else "SKIP", reason), logf)

    if should_push:
        if cfg.get("QYWX_TOKEN"):
            try:
                ok, resp = push_wecom(cfg["QYWX_TOKEN"], content)
                log("WeCom push: %s %s" % ("OK" if ok else "FAIL", resp), logf)
            except Exception as e:
                log("WeCom push ERROR: %s" % e, logf)
        elif cfg.get("PLUSPLUS_TOKEN"):
            try:
                ok, resp = push_pushplus(cfg["PLUSPLUS_TOKEN"],
                                         "\u6bcf\u65e5\u7b7e\u5230\u62a5\u544a %s" % today, content)
                log("PushPlus push: %s %s" % ("OK" if ok else "FAIL", resp), logf)
            except Exception as e:
                log("PushPlus push ERROR: %s" % e, logf)
        else:
            log("No push key configured, skipped", logf)

    # --- Step 5: 全部完成则落当日标记 ---
    if not pending and all_recs:
        save_state({
            "completed_date": today,
            "completed_at": datetime.datetime.now().strftime("%H:%M:%S"),
            "accounts": [a["name"] for a in all_recs],
        })
        log("State saved: %s marked completed" % today, logf)

    log("Check-in run finished", logf)
    logf.close()


if __name__ == "__main__":
    main()
