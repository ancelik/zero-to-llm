# Attendee guide

Step-by-step for workshop participants. Should take about 15 minutes
including the ~5–7 min training run.

## What you'll need before the workshop

1. **A laptop** with internet (Mac, Windows 10+, or Linux all work).
2. **Python 3.10 or newer** installed locally.
   - Mac: `brew install python@3.12` (or download from python.org)
   - Windows: install from [python.org](https://www.python.org/downloads/) and tick "Add Python to PATH"
   - Linux: usually already there. `python3 --version` should print 3.10+
3. **A RunPod account** at [runpod.io](https://www.runpod.io/) with at least **\$10 of credit** (the actual workshop run is around \$0.30–0.50; RunPod's minimum top-up is \$10).
4. **Your RunPod API key**, generated at [runpod.io/console/user/settings](https://www.runpod.io/console/user/settings) → "API Keys" → "+ Create API Key" → copy the value (looks like `rpa_xxxxx...`).

## Step 1 — Clone the repo

```bash
git clone https://github.com/ancelik/zero-to-llm.git
cd zero-to-llm
```

If you're not comfortable with `git`, you can instead [download a ZIP](https://github.com/ancelik/zero-to-llm/archive/refs/heads/main.zip) and unzip it.

## Step 2 — Run the local setup script

This creates a virtualenv and installs the small RunPod SDK on your laptop. *Nothing heavy is installed — PyTorch, nanochat, etc. live only on the GPU pod, not on your machine.*

**Mac / Linux:**

```bash
bash setup/setup.sh
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy Bypass -File setup\setup.ps1
```

When it finishes, it'll have created a file at `attendee/config.py` (a copy of the template).

## Step 3 — Fill in your config

Open `attendee/config.py` in your editor. Set two values:

```python
RUNPOD_API_KEY  = "rpa_..."                                 # your key from step 0
STORAGE_POD_URL = "https://abc123-8000.proxy.runpod.net"   # your workshop host gives you this URL
```

Save it. **`attendee/config.py` is gitignored**, so your key won't get committed.

## Step 4 — Verify your setup

Activate the venv first, then run the verifier:

```bash
# Mac / Linux:
source .venv/bin/activate
python setup/verify.py

# Windows (PowerShell):
.venv\Scripts\Activate.ps1
python setup\verify.py
```

You should see five `✓` checkmarks. If any fails, the error message tells you what to fix.

## Step 5 — Launch the GPU pod

You have two equivalent options depending on whether you prefer terminal or notebooks.

**Option A — terminal:**

```bash
python attendee/launch_pod.py
```

**Option B — notebook:**

```bash
jupyter notebook attendee/launch_pod.ipynb
```

…and run cells top to bottom.

Either way, after ~60 s you'll see:

```
======================================================================
  POD IS READY
======================================================================
  JupyterLab URL: https://<pod-id>-8888.proxy.runpod.net/lab
  ...
```

## Step 6 — Open JupyterLab in your browser

Click the JupyterLab URL (or copy it into a new browser tab). JupyterLab opens to `/workspace/`.

> **Background work is still happening.** When the pod first booted, it kicked off a script that's installing nanochat, downloading the SEC parquets, and prepping data. JupyterLab itself is up immediately, but the *training* notebook waits for that background work. You'll see the wait progress in the next step. Total background-install time is ~2–4 min on first boot.

## Step 7 — Run the training notebook

In the JupyterLab file browser (left sidebar), navigate to:

```
zero-to-llm/pod/02_train_workshop.ipynb
```

Open it. Run the cells **top to bottom** by clicking each cell and pressing **Shift + Enter** (or use the menu **Run → Run All Cells**).

What you'll see:

| Cell | What happens                                      | Time     |
|------|---------------------------------------------------|----------|
| 1    | Wait for background setup                         | 0–4 min  |
| 2    | Pick the SEC scope (default `all`)                | instant  |
| 3    | Re-stage data (if scope changed)                  | ~10 sec  |
| 4    | Train BPE tokenizer on SEC text                   | ~30 sec  |
| 5    | **Pretrain the GPT** — the big step               | ~5–7 min |
| 6    | Print sample completions                          | ~10 sec  |
| 7    | Custom prompts                                    | seconds  |
| 8    | Save model bundle                                 | ~10 sec  |

While Step 5 runs, you'll see lines like `step 100/400 | loss=4.85`. Loss should drop from ~7-8 down to ~3-4.

## Step 8 — Chat with your model

Open `zero-to-llm/pod/03_chat.ipynb` in JupyterLab. This is a base model (autocomplete-style), so write your prompt as the **start of a passage**, not as a question. Examples:

```
✅  ITEM 1A. RISK FACTORS

The following risks could materially affect our
```

```
❌  What are the risk factors?     # (won't work — base model doesn't do Q&A)
```

## Step 9 — (Optional) Download your model

If you ran Step 8 of the training notebook, you have `/workspace/sec_llm.tar.gz` (~30–50 MB). In JupyterLab's file browser, navigate to `/workspace/`, **right-click → Download** to save it to your laptop.

## Step 10 — Terminate the pod

⚠️ **This is important.** Idle GPU pods cost money. When you're done:

1. Go to [runpod.io/console/pods](https://www.runpod.io/console/pods).
2. Find your pod (named `zero-to-llm-attendee` by default).
3. Click the trash-can icon → **Terminate**.

You can re-launch any time by running `python attendee/launch_pod.py` again.

---

## Troubleshooting

**"None of [...] are available right now"**
The launcher couldn't find any of your preferred GPU types in stock. Edit `attendee/config.py` and add another type to `GPU_TYPE_PREFERENCE`. You can list what's available with:
```python
import runpod, attendee.config as c
runpod.api_key = c.RUNPOD_API_KEY
print(sorted(g['id'] for g in runpod.get_gpus()))
```

**"could not reach the storage pod"**
Either the host's storage pod isn't running, or the URL in your config is wrong. Ask the workshop host to confirm.

**Step 1 of the training notebook hangs forever**
The background install probably failed. Open a JupyterLab terminal (File → New → Terminal) and run `tail -50 /workspace/startup.log` to see what went wrong.

**"CUDA out of memory" during training**
Lower `--device-batch-size` (e.g. from 8 → 4) in the cell that runs `scripts.base_train`.
