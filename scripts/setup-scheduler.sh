#!/usr/bin/env bash
# Stores the GitHub token for the Supabase scheduler in Supabase Vault (hidden prompt; never printed or logged).
# Create the token first: GitHub -> Settings -> Developer settings -> Fine-grained tokens -> only repo
# Shubh-desai7/live-show-radar, permission "Actions: Read and write". Then: npm run scheduler:setup
set -euo pipefail
cd "$(dirname "$0")/.."
read -rsp "Paste the GitHub token (hidden), then press Enter: " TOKEN; echo
[ ${#TOKEN} -ge 20 ] && [[ "$TOKEN" =~ ^[A-Za-z0-9_]+$ ]] || { echo "That does not look like a GitHub token. Nothing saved."; exit 1; }
F="$(mktemp)"; chmod 600 "$F"; trap 'rm -f "$F"' EXIT
cat > "$F" <<SQL
delete from vault.secrets where name = 'github_dispatch_token';
select vault.create_secret('$TOKEN', 'github_dispatch_token', 'GitHub token used by pg_cron to dispatch workflows') is not null as stored;
SQL
npx supabase db query --remote --yes -f "$F" >/dev/null
echo "Saved to Supabase Vault (${#TOKEN} characters). Jobs run at :07/:37 (discover) and every 15 min (remind)."
