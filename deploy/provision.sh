#!/usr/bin/env bash
# ============================================================================
#  Zero to LLM — provisioner for a DigitalOcean droplet.
#
#  Gives you ONE password-protected HTTPS URL you can open from any browser:
#      https://<IP>.sslip.io/          -> the deck
#      https://<IP>.sslip.io/jupyter/  -> the kernel that actually runs train.ipynb
#
#  Same origin, so no CORS and no mixed-content problems. Caddy gets a real
#  Let's Encrypt certificate via sslip.io, so you need no domain of your own.
#
#  Security model:
#    - Caddy basic-auth guards BOTH the deck and the kernel. This endpoint
#      executes arbitrary Python; the password is what stands in front of it.
#    - The RunPod API key is injected into the kernel's systemd environment,
#      root-only (chmod 600). It is NEVER served to a browser. The notebook
#      reads it from os.environ, so there is no prompt on stage.
#    - Because the site is already behind a password, the deck can auto-connect
#      to the kernel using a token from config.json — nothing to type live.
#
#  Expects these in the environment when run:
#      RUNPOD_API_KEY   SITE_USER   SITE_PASS
#
#  Usage (on a fresh Ubuntu 24.04 droplet, as root):
#      RUNPOD_API_KEY=... SITE_USER=... SITE_PASS=... bash provision.sh
# ============================================================================
set -euo pipefail

: "${RUNPOD_API_KEY:?set RUNPOD_API_KEY}"
: "${SITE_USER:?set SITE_USER}"
: "${SITE_PASS:?set SITE_PASS}"

APP=/opt/zero-to-llm
IP="$(curl -fsS --max-time 8 https://api.ipify.org || hostname -I | awk '{print $1}')"
HOST="${IP}.sslip.io"
JTOKEN="$(openssl rand -hex 32)"

echo "==> IP   : $IP"
echo "==> host : $HOST"

# ---------------------------------------------------------------- packages
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl openssh-client \
                       debian-keyring debian-archive-keyring apt-transport-https ca-certificates

if ! command -v caddy >/dev/null 2>&1; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
    | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
    | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  apt-get update -qq
  apt-get install -y -qq caddy
fi

# ---------------------------------------------------------------- app
mkdir -p "$APP/deck" "$APP/repo/data/filings-2025-2026"

python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q jupyter-server ipykernel runpod \
                               pandas pyarrow scikit-learn matplotlib numpy ipywidgets
"$APP/venv/bin/python" -m ipykernel install --sys-prefix --name python3 >/dev/null

# SSH key the notebook registers with RunPod (its cell 3 uploads the public half)
[ -f /root/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N "" -q

# ---------------------------------------------------------------- secrets
# Root-only. Never inside the web root, never served.
umask 077
cat > "$APP/kernel.env" <<EOF
RUNPOD_API_KEY=$RUNPOD_API_KEY
EOF
chmod 600 "$APP/kernel.env"

# Served to the browser, but only from BEHIND basic auth. Lets the deck
# auto-connect so there's no token to paste on stage.
cat > "$APP/deck/config.json" <<EOF
{"jupyter": "/jupyter", "token": ""}
EOF
chmod 644 "$APP/deck/config.json"
umask 022

# ---------------------------------------------------------------- kernel service
cat > /etc/systemd/system/zt-jupyter.service <<EOF
[Unit]
Description=Zero to LLM — Jupyter kernel backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP/repo
Environment=HOME=/root
EnvironmentFile=$APP/kernel.env
ExecStart=$APP/venv/bin/jupyter server \\
  --ServerApp.ip=127.0.0.1 \\
  --ServerApp.port=8888 \\
  --ServerApp.base_url=/jupyter/ \\
  --IdentityProvider.token=$JTOKEN \\
  --ServerApp.disable_check_xsrf=True \\
  --ServerApp.allow_origin='*' \\
  --ServerApp.allow_remote_access=True \\
  --ServerApp.open_browser=False \\
  --ServerApp.allow_root=True
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

# ---------------------------------------------------------------- caddy
HASH="$(caddy hash-password --plaintext "$SITE_PASS")"
cat > /etc/caddy/Caddyfile <<EOF
$HOST {
	encode zstd gzip

	# One password in front of everything: the slides AND the kernel.
	basic_auth {
		$SITE_USER $HASH
	}

	# Kernel. Caddy handles the WebSocket upgrade automatically.
	route /jupyter/* {
		reverse_proxy 127.0.0.1:8888 {
			header_up Authorization "token $JTOKEN"
		}
	}

	root * $APP/deck
	file_server
}
EOF

systemctl daemon-reload
systemctl enable --now zt-jupyter >/dev/null
systemctl restart caddy

for i in $(seq 1 30); do
  ss -lntp 2>/dev/null | grep -q ':8888' && break
  sleep 2
done
ss -lntp 2>/dev/null | grep -q ':8888' && echo "==> kernel: listening on 8888" || {
  echo "==> kernel: FAILED"; journalctl -u zt-jupyter -n 20 --no-pager; }
systemctl is-active --quiet caddy && echo "==> caddy : up" || echo "==> caddy : FAILED"

cat <<EOF

================================================================
  https://$HOST/       user: $SITE_USER

  Still to upload from your laptop:
    scp zero-to-llm-ey.html root@$IP:$APP/deck/index.html
    rsync -avP data/filings-2025-2026/ root@$IP:$APP/repo/data/filings-2025-2026/

  On the day: open the URL, log in, press N. The runner connects
  itself, and cell 1 takes the RunPod key from the environment —
  no prompts.

  The RunPod key is in $APP/kernel.env (root-only, never served).

  DESTROY THIS DROPLET WHEN THE WORKSHOP IS OVER.
================================================================
EOF
