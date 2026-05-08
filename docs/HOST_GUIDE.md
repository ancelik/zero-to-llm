# Host guide

Pre-workshop setup for the workshop organizer (you). Run through this **once, before the workshop**.

You'll end up with:
- A small RunPod CPU pod that hosts the four SEC parquets over HTTP.
- A public URL (`https://<pod-id>-8000.proxy.runpod.net`) you'll share with attendees.

Total time: ~15 minutes.

## What you need

- Python 3.10+ on your laptop (same as for attendees — see [`ATTENDEE_GUIDE.md`](ATTENDEE_GUIDE.md)).
- A RunPod account with a small balance (the storage pod is roughly **\$0.04/hr** ≈ **\$1/day**; budget \$5–10 for a one-day workshop window).
- The four SEC parquets at `data/filings-2025-2026/`. They're already in this repo on your end.
- `scp` and `ssh-keygen` on your PATH. Mac/Linux: built in. Windows 10+: built in via the OpenSSH Client (turned on by default since 1803). If your `scp` is missing on Windows, enable it via **Settings → Apps → Optional Features → Add a feature → OpenSSH Client**.

## Step 1 — Local setup

Same as attendees:

```bash
git clone https://github.com/ancelik/zero-to-llm.git
cd zero-to-llm
bash setup/setup.sh         # or  setup\setup.ps1 on Windows
source .venv/bin/activate   # or  .venv\Scripts\Activate.ps1 on Windows
```

## Step 2 — Configure host credentials

```bash
cp host/config.example.py host/config.py
```

Open `host/config.py` and set `RUNPOD_API_KEY` to your personal key from [runpod.io/console/user/settings](https://www.runpod.io/console/user/settings).

You usually don't need to change the other fields.

## Step 3 — Deploy the storage pod

```bash
python host/deploy_storage_pod.py
```

This:
1. Generates an SSH key at `~/.ssh/id_ed25519` (if you don't already have one) and registers its public part with RunPod.
2. Creates a tiny CPU pod running `python:3.11-slim`, with `python3 -m http.server` on port 8000.
3. Waits for SSH on the pod to come up (~30–60 sec while `apt-get install openssh-server` runs in the container).
4. SCPs the four parquets up to `/data/` on the pod.
5. Verifies each parquet is reachable via the proxy URL.

When it finishes, it prints:

```
======================================================================
  STORAGE POD READY
======================================================================
  Public base URL: https://<pod-id>-8000.proxy.runpod.net
```

**Copy that URL.** This is what attendees paste into their `attendee/config.py`.

## Step 4 — Pin the URL into the attendee config template

You have two options depending on how you want attendees to discover the URL:

**(A) Bake it into the repo.** Edit `attendee/config.example.py` and replace the `STORAGE_POD_URL = "https://REPLACE_ME-8000.proxy.runpod.net"` line with your real URL. Commit + push. Attendees who clone the repo will get the URL automatically (they still need to fill in their own API key). Recommended.

**(B) Share out-of-band.** Send the URL via Slack/email/etc. and have attendees paste it into their `config.py` themselves.

## Step 5 — (Recommended) Smoke-test as an attendee

Before the workshop, do a complete dry run as if you were an attendee:

```bash
cp attendee/config.example.py attendee/config.py    # if not already
# edit attendee/config.py: paste your RunPod API key (you can use your own)
python setup/verify.py                              # all 5 checks should pass
python attendee/launch_pod.py                       # spin up a GPU pod
# open the printed JupyterLab URL, run the training notebook end-to-end
# verify the chat notebook works too
# terminate the GPU pod from the RunPod console
```

This confirms the storage pod is reachable from a freshly-spawned GPU pod, the workshop notebooks run cleanly, etc. **Do this at least 24 h before the workshop** so you have time to fix anything that's broken.

## Step 6 — During the workshop

Just keep an eye on the storage pod. If it goes down, attendees' pod-startup scripts will fail at the data-download step. You can check status at [runpod.io/console/pods](https://www.runpod.io/console/pods) (look for the pod named `zero-to-llm-storage`).

If the storage pod *does* go down mid-workshop, just re-run `python host/deploy_storage_pod.py`. It detects an existing pod and reuses it, so worst case you get a fresh one with a different URL — share the new URL with attendees.

## Step 7 — After the workshop

⚠️ **Don't leave the storage pod running indefinitely.** It's cheap (~\$1/day) but real money over weeks/months. Terminate it when the workshop window is over:

1. Go to [runpod.io/console/pods](https://www.runpod.io/console/pods).
2. Find the pod named `zero-to-llm-storage`.
3. Click the trash-can icon → **Terminate**.

---

## Alternative: HuggingFace Datasets

The RunPod CPU storage pod approach has one weakness: it's a single-VM single-point-of-failure. If you'd rather use HuggingFace Datasets (free, CDN-backed, zero maintenance), you can:

1. Install the HF CLI: `pip install huggingface_hub`
2. `huggingface-cli login` (using a write token from huggingface.co/settings/tokens)
3. `huggingface-cli upload <your-username>/sec-filings-2025-2026 ./data/filings-2025-2026 --repo-type=dataset --create-pr=false`
4. Edit `pod/startup.sh` to download from HF instead of the storage pod URL:
   ```bash
   # Replace the parquet-download loop with:
   pip install -q huggingface_hub
   python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='<your-username>/sec-filings-2025-2026', repo_type='dataset', local_dir='/workspace/sec_data')"
   ```
5. Skip running `host/deploy_storage_pod.py` entirely.

This is what I'd actually recommend for any workshop > ~10 attendees.

## Troubleshooting

**`ssh-keygen` not found on Windows**
Enable the OpenSSH Client feature: Settings → Apps → Optional Features → Add a feature → OpenSSH Client.

**`scp` upload fails with "Connection refused"**
The pod's openssh-server install may not have finished. The script polls for ~3 min; if it still fails, re-run the script (it'll detect the existing pod and retry).

**The proxy URL returns 502 Bad Gateway**
The HTTP server probably crashed or isn't running. Either reboot the pod from the RunPod console, or terminate and re-deploy.

**My RunPod account doesn't have a CPU pod option called `cpu3c-2-4`**
RunPod sometimes renames CPU instance types. List available CPU options with `runpod.get_gpus()` (the SDK lumps CPUs in too) or check the [RunPod CPU pods page](https://www.runpod.io/console/cpu-pods).
