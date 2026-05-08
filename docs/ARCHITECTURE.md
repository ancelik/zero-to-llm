# Architecture

Why is the workshop set up the way it is?

## Constraints we started from

- **Mixed OS**: attendees use Mac, Windows, and Linux. Anything OS-specific has to be either trivially portable or have parallel scripts.
- **Mixed skill level**: many attendees aren't comfortable with the terminal. Setup needs to be near one-click.
- **No local GPU required**: training runs on RunPod GPU pods, not on attendees' laptops. Local Python deps must be tiny.
- **<10 min training**: end-to-end (tokenize → pretrain → chat) finishes inside one workshop slot.
- **Cost is irrelevant** (per the original spec) but compute scarcity is real — we shouldn't request a GPU type that's frequently out of stock during a workshop.

## Why these specific choices

### Why 1×A100 80GB (and not 8×H100 like nanochat speedrun)

For a tiny ~5M-parameter model that finishes in 10 minutes, more than one GPU is wasted parallelism. A single A100 80GB has plenty of memory and is the highest-availability high-end GPU on RunPod, so 30+ attendees can spin up pods simultaneously without hitting "out of capacity."

### Why a custom BPE tokenizer instead of a pretrained one

Two reasons:
1. It's pedagogically meaningful — attendees see the *actual* speedrun pipeline, not a shortcut.
2. With a vocab of 4096 trained directly on SEC text, recurring SEC phrases ("forward-looking", " RISK FACTORS", " Item 1A.") become single tokens. The tiny model has more capacity to spend on actual structure.

The tradeoff: ~30 sec of tokenizer training. Worth it.

### Why no SFT / chat tuning

SFT would require an SEC-flavored Q&A conversation dataset, which we don't have. Pretraining alone in 5 min already gives us a recognizable autocomplete model — enough for a "wow" demo. Adding SFT would push us over 10 min and complicate the chat code.

The chat REPL therefore treats the model as autocomplete: prompts are the *start* of a passage, not questions.

### Why RunPod and not Modal / Lambda Labs / etc.

- RunPod's GPU stock and pricing are public, no quota approval needed.
- Their Python SDK supports programmatic pod creation per-user-account in one call — exactly the workshop's "each attendee uses their own account" model.
- The PyTorch image bundles JupyterLab on port 8888 by default, with a publicly-routable proxy URL (`https://<pod-id>-8888.proxy.runpod.net`). No SSH-key dance needed for attendees.

### Why three roles (host / pod / attendee) instead of two

A single shared "everyone curls from the same place" data source is way simpler than each attendee uploading 1 GB of parquets to their own pod. The storage pod is run by the host, once, and serves the workshop window.

Could it be replaced by a HuggingFace dataset? Yes — see [`HOST_GUIDE.md`](HOST_GUIDE.md) for that alternative. Trade-off discussed there too.

## Data flow

```
host's laptop
  └── data/filings-2025-2026/*.parquet
          │  (SCP via deploy_storage_pod.py)
          ▼
host's RunPod CPU storage pod
  └── /data/*.parquet  (served via python -m http.server)
          │
          │  (curl from pod/startup.sh)
          ▼
attendee's RunPod GPU pod (1× A100 80GB, runpod/pytorch:2.4 image)
  └── /workspace/
        ├── nanochat/                    (cloned by startup.sh)
        ├── zero-to-llm/                 (cloned by docker_args)
        ├── sec_data/*.parquet           (downloaded from storage pod)
        ├── ~/.cache/nanochat/
        │     ├── base_data_climbmix/    (staged by prep_sec_data.py)
        │     │     └── shard_*.parquet  (rewritten with `text` col only)
        │     ├── tokenizer/             (output of scripts.tok_train)
        │     └── base_checkpoints/      (output of scripts.base_train)
        └── startup.log                  (pod-side install + data prep log)
```

## What runs where

| Code path                          | Where it runs            | When                                    |
|------------------------------------|--------------------------|-----------------------------------------|
| `host/deploy_storage_pod.py`       | host's laptop            | once, before workshop                   |
| `setup/setup.{sh,ps1}`             | attendee's laptop        | once, when attendee clones the repo     |
| `setup/verify.py`                  | attendee's laptop        | sanity-check before launching           |
| `attendee/launch_pod.{py,ipynb}`   | attendee's laptop        | start of workshop                       |
| `pod/startup.sh`                   | attendee's GPU pod       | automatically, when pod boots           |
| `pod/prep_sec_data.py`             | attendee's GPU pod       | called by startup.sh; can re-run        |
| `pod/02_train_workshop.ipynb`      | attendee's GPU pod (Jupyter) | main workshop activity              |
| `pod/sample_generations.py`        | attendee's GPU pod       | called from the training notebook       |
| `pod/03_chat.ipynb` / `chat.py`    | attendee's GPU pod (Jupyter) | post-training                       |
| `pod/save_model.py`                | attendee's GPU pod       | optional, from training notebook        |

## What we deliberately don't do

- **No multi-GPU training.** A 5M-param model fits on one GPU comfortably; DDP overhead would dominate.
- **No FP8 / FA3.** Both require Hopper (H100+); on A100 we use bfloat16 + PyTorch SDPA. nanochat handles this gracefully.
- **No wandb integration.** `--run dummy` skips it. Running a wandb account per attendee is a nightmare we don't want.
- **No auto-shutdown.** The user explicitly chose "manual" — attendees terminate via the RunPod console when done. The training notebook has a big reminder.
- **No SSH from attendee laptops.** All pod interaction happens through the JupyterLab proxy URL in the browser. SSH is reserved for the host's data-upload step.
