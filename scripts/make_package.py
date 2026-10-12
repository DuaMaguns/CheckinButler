#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_package.py - 把项目打成可分享的 zip，自动排除一切敏感/运行时文件。

排除规则（宁可多排，不可漏排）：
  - config/checkin_env.bat            推送密钥
  - config/trae-accounts/*.json       Trae 凭证归档
  - scripts/workbuddy-checkin/auths/  WorkBuddy 凭证（保留 auth.example.json）
  - scripts/Qoder-Checkin/accounts.json / config.json / 缓存
  - logs/ 全部、各状态文件、__pycache__、.git、打包产物目录

用法：python scripts/make_package.py   （产物在 dist/CheckinButler-YYYYMMDD-HHMM.zip）
"""
import datetime
import os
import sys
import zipfile

TOOL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(TOOL_DIR, "dist")

EXCLUDE_DIRS = {"__pycache__", ".git", ".idea", ".vscode", "logs", "dist"}
EXCLUDE_FILES = {
    "checkin_env.bat",
    "accounts.json",
    "config.json",                 # Qoder 设备标识（模板里只留 config.example.json）
    ".qoder_token_cache.json",
    ".checkin_state.json",
    ".trae_checkin_state.json",
    ".trae_device_ids.json",
}
# WorkBuddy auths 目录：只保留 example
AUTHS_DIR = os.path.join(TOOL_DIR, "scripts", "workbuddy-checkin", "auths")


def excluded(path):
    rel = os.path.relpath(path, TOOL_DIR).replace("\\", "/")
    parts = rel.split("/")
    if any(p in EXCLUDE_DIRS for p in parts):
        return True
    name = os.path.basename(path)
    if name in EXCLUDE_FILES:
        return True
    if rel.startswith("scripts/workbuddy-checkin/auths/") and name != "auth.example.json":
        return True
    if name.endswith((".pyc", ".log", ".zip")):
        return True
    return False


def main():
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    out = os.path.join(DIST, "CheckinButler-%s.zip" % stamp)
    os.makedirs(DIST, exist_ok=True)
    n = 0
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(TOOL_DIR):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
            for f in files:
                p = os.path.join(root, f)
                if excluded(p):
                    continue
                arc = os.path.join("checkin-tool", os.path.relpath(p, TOOL_DIR))
                z.write(p, arc)
                n += 1
    size = os.path.getsize(out) / 1024
    print("✅ 打包完成：%s" % out)
    print("   %d 个文件，%.0f KB" % (n, size))
    print("   已排除：凭证、推送密钥、日志、状态文件、缓存")
    # 简单自检：zip 内不得出现敏感文件名
    with zipfile.ZipFile(out) as z:
        bad = [x for x in z.namelist()
               if x.endswith(("checkin_env.bat", "accounts.json", "config.json"))
               and "example" not in x]
    if bad:
        print("❌ 自检失败，以下敏感文件被误打包（请立即删除该 zip）：")
        for b in bad:
            print("   " + b)
        return 1
    print("   自检通过：无敏感文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
