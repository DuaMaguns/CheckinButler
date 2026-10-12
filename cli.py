#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py - 签到管家 CheckinButler 交互主程序（纯标准库，零第三方依赖）

首次使用：自动进入逐项引导向导（自检 → 绑推送 → 加账号 → 建定时任务 → 试跑）
日常使用：数字菜单，单项操作随来随办

直接运行：python cli.py        （或双击根目录 cli.bat）
"""
import datetime
import glob
import io
import json
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TOOL_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(TOOL_DIR, "scripts")
WB_DIR = os.path.join(SCRIPTS, "workbuddy-checkin")
TRAE_DIR = os.path.join(SCRIPTS, "Trae-AutoCheckin")
QODER_DIR = os.path.join(SCRIPTS, "Qoder-Checkin")
CONFIG = os.path.join(TOOL_DIR, "config", "checkin_env.bat")
CONFIG_EXAMPLE = os.path.join(TOOL_DIR, "config", "checkin_env.example.bat")
LOG_DIR = os.path.join(TOOL_DIR, "logs")

TASK_NAME = "CheckinTool"
WECOM_BASE = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key="
PUSHPLUS_URL = "https://www.pushplus.plus/send"

import urllib.request


# ------------------------------------------------------------------ ui

def hr(ch="─", n=56):
    print(ch * n)


def title(txt):
    print()
    hr("═")
    print("  %s" % txt)
    hr("═")


def ask(prompt, default="", allow_empty=False):
    while True:
        s = input("%s%s: " % (prompt,
                              (" [回车=%s]" % default) if default else "")).strip()
        if s:
            return s
        if default:
            return default
        if allow_empty:
            return ""


def confirm(prompt, default=False):
    d = "Y" if default else "N"
    s = input("%s [y/N，回车=%s]: " % (prompt, d)).strip().lower()
    return s in ("y", "yes", "是")


def pause():
    input("\n回车返回菜单...")


def run_py(args, cwd=None, capture=True, timeout=300):
    """运行同解释器的另一个脚本，返回 (returncode, output)。capture=False 时直接继承控制台。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if capture:
        r = subprocess.run([sys.executable] + args, cwd=cwd or TOOL_DIR, env=env,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    r = subprocess.call([sys.executable] + args, cwd=cwd or TOOL_DIR, env=env)
    return r, ""


# ------------------------------------------------------------------ config

def load_cfg():
    cfg = {}
    try:
        raw = io.open(CONFIG, encoding="utf-8", errors="replace").read()
    except OSError:
        return cfg
    for line in raw.splitlines():
        m = re.match(r'^\s*set\s+"?([A-Za-z_][A-Za-z0-9_]*)=(.*?)"?\s*$', line)
        if m:
            v = m.group(2)
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            cfg[m.group(1)] = v
    return cfg


def write_config_key(key, value):
    """把 set "KEY=VALUE" 写进 checkin_env.bat（不存在则从 example 复制后写）。"""
    os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
    if not os.path.isfile(CONFIG):
        if os.path.isfile(CONFIG_EXAMPLE):
            raw = io.open(CONFIG_EXAMPLE, encoding="utf-8", errors="replace").read()
        else:
            raw = "REM checkin_env.bat - 本地配置（含密钥，勿外传）\n"
    else:
        raw = io.open(CONFIG, encoding="utf-8", errors="replace").read()
    lines = raw.splitlines()
    pat = re.compile(r'^(\s*set\s+"?%s)=.*("?)\s*$' % re.escape(key))
    new_line = 'set "%s=%s"' % (key, value)
    replaced = False
    out = []
    for ln in lines:
        if pat.match(ln):
            out.append(new_line)
            replaced = True
        else:
            out.append(ln)
    if not replaced:
        out.append(new_line)
    with io.open(CONFIG, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


# ------------------------------------------------------------------ push

def extract_wecom_key(text):
    """从完整 webhook URL 或裸 key 中提取 key 段。"""
    text = text.strip().strip('"')
    m = re.search(r"key=([A-Za-z0-9\-]{16,})", text)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9\-]{16,}", text):
        return text
    return ""


def test_wecom(key):
    payload = {"msgtype": "markdown",
               "markdown": {"content": "**✅ 签到管家推送测试成功**\n配置时间：%s"
                                        % datetime.datetime.now().strftime("%Y-%m-%d %H:%M")}}
    req = urllib.request.Request(
        WECOM_BASE + key,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read().decode())
        return d.get("errcode") == 0, d


def setup_push():
    """交互式绑定企业微信 / PushPlus，当场试发验证。"""
    title("步骤 · 绑定推送渠道")
    print("支持两种渠道：企业微信消息推送(群机器人)（推荐）/ PushPlus")
    ch = ask("选 1=企业微信  2=PushPlus  0=跳过", default="1")
    if ch == "0":
        print("已跳过。之后可在菜单「绑定推送」里随时配置。")
        return False
    if ch == "2":
        tok = ask("粘贴 PushPlus 的 token（www.pushplus.plus 首页可复制）")
        if not tok:
            return False
        write_config_key("PLUSPLUS_TOKEN", tok)
        write_config_key("QYWX_TOKEN", "")
        print("✅ PLUSPLUS_TOKEN 已写入配置（PushPlus 无即时验证，日报发出后注意查收）")
        return True
    # 企业微信
    print("\n获取方法：微信群 → 右键 → 添加消息推送(群机器人) → 新建，复制 Webhook 地址")
    print("          （新版企业微信叫「消息推送」，旧版叫「群机器人」，是同一个东西）")
    raw = ask("粘贴 Webhook 地址（或只粘贴 key= 后面那段）")
    key = extract_wecom_key(raw)
    if not key:
        print("❌ 没能识别出 key。Webhook 长这样：")
        print("   https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxxx-xx-xx")
        return False
    print("识别到 key：%s...%s，正在试发验证消息..." % (key[:8], key[-6:]))
    try:
        ok, resp = test_wecom(key)
    except Exception as e:
        print("❌ 发送失败：%s" % e)
        print("   请检查网络 / key 是否完整 / 机器人是否被删除")
        return False
    if not ok:
        print("❌ 企业微信返回异常：%s" % resp)
        if resp.get("errcode") == 93000:
            print("   93000 = key 无效，请重新复制完整 Webhook 地址")
        return False
    write_config_key("QYWX_TOKEN", key)
    print("✅ 验证通过！已写入 QYWX_TOKEN。请看一眼微信群，应收到一条测试消息。")
    return True


# ------------------------------------------------------------------ accounts

def wb_count():
    return len([p for p in glob.glob(os.path.join(WB_DIR, "auths", "workbuddy-*.json"))])


def trae_count():
    try:
        d = json.load(io.open(os.path.join(QODER_DIR, "accounts.json"), encoding="utf-8"))
        qn = len(d.get("accounts", []))
    except Exception:
        qn = 0
    n = 0
    cfgv = load_cfg().get("TRAE_ACCOUNTS", "")
    if cfgv:
        try:
            n = len(json.loads(cfgv))
        except Exception:
            n = 0
    return n, qn


def account_summary():
    try:
        nwb = wb_count()
    except Exception:
        nwb = 0
    nt, nq = trae_count()
    return nwb, nt, nq


def add_workbuddy():
    title("添加 WorkBuddy 账号")
    print("流程：脚本打印授权链接 → 你在浏览器无痕窗口登录 → 凭证自动落盘")
    print("⚠️  务必用无痕窗口，且每个账号跑一次本流程\n")
    input("回车开始，将打开授权流程（登录页面跳 127.0.0.1 报错属正常）...")
    run_py(["login_quick.py"], cwd=WB_DIR, capture=False)
    print("\n当前 WorkBuddy 账号数：%d" % wb_count())


def add_trae():
    title("添加 Trae 账号")
    print("前提：Trae 客户端已登录目标账号（本工具会自动识别客户端登录态）")
    print("多账号：客户端切换登录后，再跑一次本项\n")
    input("回车开始归档...")
    run_py(["trae_accounts_update.py"], cwd=SCRIPTS, capture=False)
    n, _ = trae_count()
    print("当前 Trae 配置账号数：%d" % n)


def add_qoder():
    title("添加 Qoder 账号")
    print("前提：本机装了 Qoder 客户端且已登录")
    print("多账号：客户端切换登录后，再跑一次本项\n")
    input("回车开始提取...")
    run_py(["01_extract.py"], cwd=QODER_DIR, capture=False)
    _, nq = trae_count()
    print("当前 Qoder 账号数：%d" % nq)


def add_accounts_wizard():
    title("步骤 · 添加账号")
    nwb, nt, nq = account_summary()
    print("当前已有：WorkBuddy %d 个 · Trae %d 个 · Qoder %d 个" % (nwb, nt, nq))
    print("哪几个平台要加号？（加号流程需要你在浏览器/客户端配合）")
    want = ask("输入组合，如 1,3=WorkBuddy+Qoder；直接回车=跳过", allow_empty=True)
    want = {x.strip() for x in want.replace("，", ",").split(",") if x.strip()}
    if "1" in want:
        add_workbuddy()
    if "2" in want:
        add_trae()
    if "3" in want:
        add_qoder()
    if not want:
        print("已跳过加号，之后可在菜单里随时添加。")


# ------------------------------------------------------------------ schtasks

def _schtasks(args):
    """执行 schtasks，返回 (成功?, 输出)。命令不存在/被拦截时安全降级。"""
    try:
        r = subprocess.run(["schtasks"] + args, capture_output=True,
                           text=True, errors="replace", timeout=30)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def task_exists():
    ok, _ = _schtasks(["/query", "/tn", TASK_NAME])
    return ok


def task_create(hhmm):
    bat = os.path.join(TOOL_DIR, "run_checkin.bat")
    return _schtasks(["/create", "/f", "/tn", TASK_NAME,
                      "/tr", '"%s"' % bat, "/sc", "daily", "/st", hhmm])


def task_delete():
    return _schtasks(["/delete", "/f", "/tn", TASK_NAME])


def task_info():
    return _schtasks(["/query", "/tn", TASK_NAME, "/v", "/fo", "LIST"])


def valid_hhmm(s):
    return bool(re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", s.strip()))


def setup_task():
    title("定时任务（Windows 计划任务）")
    exists = task_exists()
    if exists:
        ok, info = task_info()
        for ln in (info or "").splitlines():
            if re.search("任务名|Task To Run|开始时间|Start Time|上次运行|Last Run|下次运行|Next Run|状态|Status", ln):
                print("  " + ln.strip())
        print()
        print("  1 = 修改执行时间    2 = 删除任务    0 = 返回")
        ch = ask("选择", default="0")
        if ch == "1":
            hhmm = ask("每天几点执行（HH:MM，如 09:00）")
            if not valid_hhmm(hhmm):
                print("❌ 时间格式不对")
                return
            ok, msg = task_create(hhmm)
            print(("✅ 已更新：" if ok else "❌ 失败：") + msg.strip())
        elif ch == "2":
            if confirm("确认删除定时任务 %s？" % TASK_NAME):
                ok, msg = task_delete()
                print(("✅ 已删除" if ok else "❌ 失败：") + msg.strip())
    else:
        print("尚未创建定时任务。")
        hhmm = ask("每天几点自动签到？（HH:MM，如 09:00，回车跳过）",
                   default="09:00")
        if not valid_hhmm(hhmm):
            print("❌ 时间格式不对，未创建")
            return
        ok, msg = task_create(hhmm)
        if ok:
            print("✅ 定时任务已创建：每天 %s 自动执行 run_checkin.bat" % hhmm)
            print("   任务名：%s（菜单里可随时改时间或删除）" % TASK_NAME)
        else:
            print("❌ 创建失败：%s" % msg.strip())
            print("   可按 docs\\03-定时任务.md 手动配置")


# ------------------------------------------------------------------ misc actions

def show_credits():
    title("账号积分总览")
    ok, out = run_py(["workbuddy_checkin.py", "credit"], cwd=WB_DIR)
    print(out.strip() or "(无输出)")
    print()
    ok, out = run_py(["trae_credit_monitor.py"], cwd=TRAE_DIR)
    print(out.strip()[:2000] or "(Trae 无输出)")
    pause()


def run_now():
    title("立即签到一次")
    if not confirm("将真实执行三平台签到（已签的会幂等跳过），并推送日报，继续？"):
        return
    run_py(["run_all.py"], cwd=SCRIPTS, capture=False)
    print("\n完成。日报推送结果见上面输出，详细日志在 logs\\ 目录。")


def show_logs():
    title("运行日志")
    files = sorted(glob.glob(os.path.join(LOG_DIR, "checkin_*.log")), reverse=True)
    if not files:
        print("还没有日志。先跑一次签到。")
        pause()
        return
    for i, p in enumerate(files[:5]):
        print("  %d = %s" % (i + 1, os.path.basename(p)))
    ch = ask("看哪天的？（1-5，回车=最新）", default="1")
    try:
        pick = files[max(0, min(int(ch) - 1, len(files) - 1))]
    except ValueError:
        pick = files[0]
    print()
    tail = ask("看最后多少行？", default="40")
    try:
        n = max(5, min(int(tail), 400))
    except ValueError:
        n = 40
    lines = io.open(pick, encoding="utf-8", errors="replace").read().splitlines()
    print("--- %s（共 %d 行，显示最后 %d 行）---" % (os.path.basename(pick), len(lines), n))
    for ln in lines[-n:]:
        print(ln)
    pause()


def doctor_run():
    title("环境自检")
    sys.path.insert(0, SCRIPTS)
    try:
        import doctor  # noqa
    except Exception as e:
        print("无法加载 doctor.py：%s" % e)
        return []
    doctor.check_python()
    cfg = doctor.check_config()
    doctor.check_trae.cfg = cfg
    print()
    doctor.check_workbuddy()
    print()
    doctor.check_qoder()
    print()
    doctor.check_trae()
    print()
    doctor.check_network()
    return list(doctor.problems)


# ------------------------------------------------------------------ wizard

def is_initialized():
    cfg = load_cfg()
    has_push = bool(cfg.get("QYWX_TOKEN") or cfg.get("PLUSPLUS_TOKEN"))
    nwb, nt, nq = account_summary()
    return has_push and (nwb + nt + nq) > 0


def wizard():
    print()
    hr("═")
    print("  🎯 检测到首次使用 —— 引导向导（约 5 分钟，全程回车+粘贴即可）")
    hr("═")
    input("\n回车开始...")

    print("\n【1/5】环境自检")
    problems = doctor_run()
    if problems:
        print("\n⚠️ 自检发现 %d 个问题（加账号等步骤会解决其中大部分，可继续）" % len(problems))

    print("\n【2/5】绑定企业微信推送")
    setup_push()

    print("\n【3/5】添加账号")
    add_accounts_wizard()

    print("\n【4/5】配置定时任务")
    setup_task()

    print("\n【5/5】试跑一次")
    nwb, nt, nq = account_summary()
    if nwb + nt + nq:
        if confirm("现在真实跑一次签到并推送日报？"):
            run_py(["run_all.py"], cwd=SCRIPTS, capture=False)
    else:
        print("还没有任何账号，跳过试跑。回菜单加号后再跑。")

    print()
    hr("═")
    print("  🎉 向导结束！之后每天定时自动签到 + 推送，无需人工干预。")
    print("     日常管理回到本菜单即可：加号 / 改推送时间 / 查积分 / 看日志。")
    hr("═")
    pause()


# ------------------------------------------------------------------ menu

MENU = """
┌──────────────────────────────────────────────┐
│           签到管家 · 控制台                    │
├──────────────────────────────────────────────┤
│  1. 环境自检          2. 添加 WorkBuddy 账号  │
│  3. 添加 Trae 账号    4. 添加 Qoder 账号      │
│  5. 绑定/修改推送     6. 定时任务（建/改/删）  │
│  7. 立即签到一次      8. 账号积分总览          │
│  9. 查看日志          0. 退出                 │
└──────────────────────────────────────────────┘"""


def menu():
    while True:
        nwb, nt, nq = account_summary()
        cfg = load_cfg()
        push = "企业微信" if cfg.get("QYWX_TOKEN") else (
            "PushPlus" if cfg.get("PLUSPLUS_TOKEN") else "未配置")
        task = "已建" if task_exists() else "未建"
        print(MENU)
        print("  当前：WB %d · Trae %d · Qoder %d ｜推送 %s ｜定时任务 %s"
              % (nwb, nt, nq, push, task))
        ch = input("\n请选择: ").strip()
        if ch == "1":
            doctor_run()
            pause()
        elif ch == "2":
            add_workbuddy()
            pause()
        elif ch == "3":
            add_trae()
            pause()
        elif ch == "4":
            add_qoder()
            pause()
        elif ch == "5":
            setup_push()
            pause()
        elif ch == "6":
            setup_task()
            pause()
        elif ch == "7":
            run_now()
            pause()
        elif ch == "8":
            show_credits()
        elif ch == "9":
            show_logs()
        elif ch == "0":
            print("Bye.")
            return
        else:
            print("无效选择")


def main():
    print()
    hr("═")
    print("  签到管家 CheckinButler  ·  %s" % TOOL_DIR)
    hr("═")
    if "--wizard" in sys.argv or not is_initialized():
        wizard()
    menu()


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n已退出。")
