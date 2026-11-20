#!/usr/bin/env bash
# Saves TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME into .env.local.
# The token is typed hidden, verified with Telegram's getMe, and never printed.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=".env.local"
[ -f "$ENV_FILE" ] || { echo "No $ENV_FILE found. Run: cp .env.example .env.local"; exit 1; }

read -rsp "Paste your bot token (input is hidden), then press Enter: " TOKEN; echo
[[ "$TOKEN" =~ ^[0-9]+:[A-Za-z0-9_-]{30,}$ ]] || { echo "That doesn't look like a Telegram bot token (expected 123456789:AA...)."; exit 1; }

RESP=$(curl -s --max-time 15 "https://api.telegram.org/bot${TOKEN}/getMe" || true)
USERNAME=$(TG_RESP="$RESP" python3 -c 'import json,os
try:
    d=json.loads(os.environ["TG_RESP"])
    print(d["result"]["username"] if d.get("ok") else "")
except Exception:
    print("")')
[ -n "$USERNAME" ] || { echo "Telegram rejected that token. Nothing was saved. Copy it again from @BotFather."; exit 1; }

TG_TOKEN="$TOKEN" TG_USER="$USERNAME" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path = sys.argv[1]
s = open(path).read()
for key, val in (("TELEGRAM_BOT_TOKEN", os.environ["TG_TOKEN"]), ("TELEGRAM_BOT_USERNAME", os.environ["TG_USER"])):
    if re.search(r"^%s=.*$" % key, s, re.M):
        s = re.sub(r"^%s=.*$" % key, lambda m: "%s=%s" % (key, val), s, flags=re.M)
    else:
        s += "\n%s=%s\n" % (key, val)
open(path, "w").write(s)
PY
echo "Saved. Bot @${USERNAME} is configured in $ENV_FILE."
