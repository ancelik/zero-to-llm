# Presenting from anywhere (browser only)

The deck can run `train.ipynb` **inside itself** — press `N`. But a browser tab
cannot open an SSH connection, and the notebook's entire job is to SSH into a
RunPod box. So the deck doesn't try to run Python. It drives a **real Jupyter
kernel** over Jupyter's REST + WebSocket API, and *that* kernel does the SSH,
the upload, and the training.

That kernel can live in one of two places.

---

## Option A — laptop (simplest, fine if you're presenting from your own machine)

```bash
cd code/zero-to-llm-main
source .venv/bin/activate
pip install jupyter-server ipykernel

jupyter server \
  --ServerApp.port=8888 \
  --IdentityProvider.token=zerotollm \
  --ServerApp.allow_origin='*' \
  --ServerApp.disable_check_xsrf=True
```

Open the deck, press `N`, connect to `http://localhost:8888` with token `zerotollm`.

The catch: uploading the SEC parquets to the GPU pod goes over **your** internet
connection. On conference wifi, that is the single most likely way the live demo
dies.

---

## Option B — DigitalOcean droplet (present from any browser, anywhere)

One HTTPS URL. Nothing installed on the machine you present from — borrow a
laptop, use a lectern PC, it doesn't matter.

It also fixes the upload problem: the parquets already sit in a datacenter, so
the transfer to the RunPod pod is datacenter-to-datacenter.

### 1. Create the droplet

Ubuntu 24.04, `s-2vcpu-4gb`. Billed hourly — a workshop costs cents.

```bash
doctl compute droplet create zero-to-llm \
  --image ubuntu-24-04-x64 --size s-2vcpu-4gb --region nyc3 \
  --ssh-keys <your-key-id> --wait
```

### 2. Provision it

```bash
scp deploy/provision.sh root@<IP>:/root/
ssh root@<IP> 'bash /root/provision.sh'
```

This installs Python + Jupyter + Caddy, generates an SSH key for RunPod, and
prints a **token**. Caddy gets a real Let's Encrypt certificate using
`<IP>.sslip.io`, so you need no domain of your own.

### 3. Push the deck and the data

```bash
scp zero-to-llm-ey.html root@<IP>:/opt/zero-to-llm/deck/index.html

# 12 MB — this is all the training run needs
scp data/filings-2025-2026/market_risk_2025_2026.parquet \
    root@<IP>:/opt/zero-to-llm/repo/data/filings-2025-2026/

# the other three (~966 MB) are only needed for the embeddings section
```

### 4. Present

Open `https://<IP>.sslip.io/` in any browser. Press `N`. The server URL is
already filled in (the deck and the kernel are the same origin). Paste the
token, hit **Connect**, and run the cells.

---

## What the runner gives you

- The real notebook's 23 code cells, labelled by section, run one at a time
  (`⇧⏎` = run and advance).
- Streaming stdout, exactly as the kernel produces it.
- **A live loss curve**, parsed straight out of nanochat's
  `step N/400 | loss=…` output as it streams. This is the moment the whole talk
  is built around, and it draws itself.
- The `getpass` RunPod-key prompt appears as a masked field in the deck.
- Matplotlib figures (PCA, t-SNE) render inline in the output pane.
- `Interrupt` and `Restart kernel` for when it goes wrong on stage.

## Security — read this

The droplet exposes an endpoint that **executes arbitrary Python**, protected by
one token. That is a genuine remote-code-execution surface.

- The token is 32 random bytes. Don't paste it into chat, slides, or a shared doc.
- Your RunPod API key is typed at runtime via `getpass` and is **never written to
  disk** on the droplet.
- **Destroy the droplet when the workshop ends:**
  ```bash
  doctl compute droplet delete zero-to-llm
  ```
- Remember the last notebook cell terminates the GPU pod. An idle A100 bills all night.
