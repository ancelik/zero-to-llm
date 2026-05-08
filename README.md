# zero-to-llm

A workshop kit for training a tiny LLM end-to-end on SEC filings, using
[Karpathy's nanochat](https://github.com/karpathy/nanochat) running on a
RunPod GPU. The whole training pipeline (custom BPE tokenizer + GPT
pretraining + interactive chat) finishes in **under 10 minutes** on a single
A100.

```
                 ┌──────────────────────────────────────┐
                 │  attendee's laptop (mac/win/linux)   │
                 │  - opens 01_launch_pod.ipynb / .py   │
                 │  - pastes their RunPod API key       │
                 └──────────────────────────────────────┘
                             │ runpod SDK call
                             ▼
                 ┌──────────────────────────────────────┐
                 │  attendee's RunPod GPU (1× A100 80GB)│
                 │  - clones nanochat + this repo       │
                 │  - downloads SEC parquets from HOST  │
                 │  - runs 02_train_workshop notebook   │
                 │  - runs 03_chat notebook             │
                 └──────────────────────────────────────┘
                             ▲
                             │ wget parquets
                             │
                 ┌──────────────────────────────────────┐
                 │  HOST's RunPod CPU storage pod       │
                 │  (you, the workshop organizer)       │
                 │  - serves SEC parquets over HTTP     │
                 └──────────────────────────────────────┘
```

## Two roles

- **Workshop host (you)** — set up once, before the workshop. See
  [docs/HOST_GUIDE.md](docs/HOST_GUIDE.md).
- **Workshop attendee** — runs through the launcher + notebooks during the
  workshop. See [docs/ATTENDEE_GUIDE.md](docs/ATTENDEE_GUIDE.md).

## Repo layout

| Path | What runs it | Purpose |
|---|---|---|
| `attendee/` | attendee's laptop | local launcher (.py + .ipynb), config template |
| `pod/` | the GPU pod | training + chat notebooks (and .py equivalents) |
| `host/` | host's laptop, once | deploy the public storage pod, upload data |
| `setup/` | attendee's laptop, once | cross-platform local environment setup |
| `data/` | host's laptop | the four SEC parquet files |
| `docs/` | reading material | step-by-step guides |

## Quickstart

**Attendees**: read [`docs/ATTENDEE_GUIDE.md`](docs/ATTENDEE_GUIDE.md). The
short version is:

```bash
# 1. Clone this repo
git clone https://github.com/ancelik/zero-to-llm.git && cd zero-to-llm
# 2. One-time local setup (mac/linux)
bash setup/setup.sh
#    or on Windows (PowerShell):
#    powershell -ExecutionPolicy Bypass -File setup\setup.ps1
# 3. Copy the config template and add your RunPod API key
cp attendee/config.example.py attendee/config.py   # then edit
# 4. Launch the pod (either of these)
python attendee/launch_pod.py
#    or open attendee/launch_pod.ipynb in Jupyter
# 5. Open the printed Jupyter URL in your browser
# 6. Run 02_train_workshop.ipynb on the pod, then 03_chat.ipynb
```

**Hosts**: read [`docs/HOST_GUIDE.md`](docs/HOST_GUIDE.md).

## Architecture & design notes

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the why.
