@echo off
REM ============================================================
REM  checkin_env.example.bat — 配置文件模板
REM
REM  用法：
REM    1. 把本文件复制一份，命名为 checkin_env.bat（同目录）
REM    2. 逐项填写下面的值
REM    3. 双击运行 setup.bat 做一次自检
REM
REM  ⚠ 安全提示
REM    - checkin_env.bat 里全是密钥（refreshToken / webhook / 私钥）
REM   - 它是 .gitignore 忽略项，绝对不要提交到 git 或发给别人
REM    - 本 example 文件可以安全提交
REM ============================================================

REM ──────────────────────────────────────────────────────────
REM  一、Trae 账号（不用手填，脚本生成）
REM ──────────────────────────────────────────────────────────
REM  生成方式：
REM    1) 打开 Trae 客户端，登录账号 1
REM    2) 双击 get_tokens.bat
REM    3) 把屏幕上打印的这一整行原样粘到这里
REM    4) 换账号 2 登录，再跑一次 get_tokens.bat，把新行合并进来
REM
REM  TRAE_ACCOUNTS 是一个 JSON 数组，多个账号用逗号隔开：
REM    [{"refreshToken":"xxx","uid":"111","name":"账号1"},
REM     {"refreshToken":"yyy","uid":"222","name":"账号2"}]
REM
set "TRAE_ACCOUNTS=[]"

REM ──────────────────────────────────────────────────────────
REM  二、Trae 设备密钥（同样由 get_tokens.bat 生成，原样粘贴）
REM ──────────────────────────────────────────────────────────
REM  说明：设备密钥用于 token 续期，丢了大不了重新生成一次，
REM        但和 refreshToken 一样属于敏感信息，别外传。
REM
set "TRAE_DEVICE_KEY_PEM="
set "TRAE_DEVICE_PUB_PEM="
set "TRAE_DEVICE_ID="
set "TRAE_MACHINE_ID="

REM ──────────────────────────────────────────────────────────
REM  三、通知推送（二选一，都填则优先企业微信）
REM ──────────────────────────────────────────────────────────
REM
REM  【企业微信消息推送(群机器人)】推荐
REM    群设置 → 消息推送(群机器人) → 添加 → 复制 Webhook 地址
REM    整段粘进来即可（key= 后面那串才是真正用的部分，脚本会自己截）
REM
set "QYWX_TOKEN="
REM
REM  【PushPlus】兜底方案
REM    pushplus.plus 微信扫码登录 → 复制 token
REM
set "PLUSPLUS_TOKEN="

REM ──────────────────────────────────────────────────────────
REM  四、WorkBuddy 桌面端路径（用于从客户端抽取登录态）
REM ──────────────────────────────────────────────────────────
REM  在 WorkBuddy 客户端里点「帮助 → 关于」能看到安装位置，
REM  或者在任务管理器里右键进程 → 打开文件所在位置。
REM  留空也不影响：login_quick.py 走浏览器授权，不需要这个。
REM
set "WORKBUDDY_EXE="

REM ──────────────────────────────────────────────────────────
REM  五、可选：Trae 行为微调
REM ──────────────────────────────────────────────────────────
REM  9074 冷却分钟数（默认：平时 55，早高峰 12）
REM set "TRAE_COOLDOWN_MIN=55"
REM set "TRAE_PEAK_COOLDOWN_MIN=12"
REM
REM  账号间随机错峰开关（默认 1 开启，设 0 关闭）
REM set "TRAE_JITTER=1"
REM
REM  9074 时是否自动换设备号重试（默认 1 开启）
REM set "TRAE_ROTATE=1"
REM
REM  熔断：一个账号被限流就跳过其余账号（默认 0 关闭）
REM set "TRAE_CIRCUIT=0"
