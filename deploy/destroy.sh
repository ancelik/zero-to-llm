#!/usr/bin/env bash
# ============================================================================
#  Destroy the workshop droplet. Run this when the workshop is over.
#
#  The droplet bills by the hour until it is deleted, and it is a public
#  endpoint that executes Python and holds your RunPod key. Don't leave it up.
#
#      bash destroy.sh
# ============================================================================
set -euo pipefail

SECRETS="${HOME}/.secrets/zero-to-llm.env"
[ -f "$SECRETS" ] || { echo "no $SECRETS"; exit 1; }
set -a; . "$SECRETS"; set +a
: "${DO_TOKEN:?DO_TOKEN not set}"

API="https://api.digitalocean.com/v2"
AUTH=(-H "Authorization: Bearer $DO_TOKEN")

# Only ever touch droplets named exactly this. Never anything else.
NAME="ey-zero-to-llm"

ID=$(curl -fsS "${AUTH[@]}" "$API/droplets?per_page=200" | python3 -c "
import sys, json
ds = json.load(sys.stdin)['droplets']
m = [d for d in ds if d['name'] == '$NAME']
print(m[0]['id'] if m else '')
")

if [ -z "$ID" ]; then
  echo "no droplet named '$NAME' — nothing to destroy"
  exit 0
fi

echo "about to DESTROY droplet '$NAME' (id=$ID)"
read -rp "type the droplet name to confirm: " CONFIRM
[ "$CONFIRM" = "$NAME" ] || { echo "aborted"; exit 1; }

curl -fsS -X DELETE "${AUTH[@]}" "$API/droplets/$ID"
echo "destroyed droplet $ID"

# The SSH key is harmless to keep, but remove it if you like:
#   curl -X DELETE "${AUTH[@]}" "$API/account/keys/<id>"

echo
echo "Reminder: if you ran the notebook, make sure the RunPod POD is also gone."
echo "The last notebook cell terminates it — an idle A100 bills all night."
