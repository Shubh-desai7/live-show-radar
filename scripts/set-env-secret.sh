#!/usr/bin/env bash
# Saves one secret into .env.local with a hidden prompt (never printed, never in shell history).
# Usage: bash scripts/set-env-secret.sh JAMBASE_API_KEY   (or TICKETMASTER_API_KEY, ...)
set -euo pipefail
cd "$(dirname "$0")/.."
NAME="${1:-}"
[[ "$NAME" =~ ^[A-Z][A-Z0-9_]{2,60}$ ]] || { echo "Usage: $0 NAME   (UPPER_SNAKE_CASE, e.g. JAMBASE_API_KEY)"; exit 1; }
ENV_FILE=".env.local"
[ -f "$ENV_FILE" ] || { echo "No $ENV_FILE found."; exit 1; }
read -rsp "Paste the value for $NAME (hidden), then press Enter: " VALUE; echo
[ ${#VALUE} -ge 8 ] || { echo "That looks too short. Nothing saved."; exit 1; }
[[ "$VALUE" != *$'\n'* ]] || { echo "Value must be one line. Nothing saved."; exit 1; }
SECRET_NAME="$NAME" SECRET_VALUE="$VALUE" python3 - "$ENV_FILE" <<'PY'
import os, re, sys
path, key, val = sys.argv[1], os.environ["SECRET_NAME"], os.environ["SECRET_VALUE"]
s = open(path).read()
if re.search(r"^%s=.*$" % re.escape(key), s, re.M):
    s = re.sub(r"^%s=.*$" % re.escape(key), lambda m: "%s=%s" % (key, val), s, flags=re.M)
else:
    s += ("" if s.endswith("\n") else "\n") + "%s=%s\n" % (key, val)
open(path, "w").write(s)
PY
echo "Saved $NAME in $ENV_FILE (${#VALUE} characters)."
