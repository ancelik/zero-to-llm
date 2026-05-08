"""
Attendee config template.

Copy to `attendee/config.py` and fill in the two values below.
`attendee/config.py` is gitignored, so your API key won't be committed.
"""

# YOUR personal RunPod API key.
# Get one at: https://www.runpod.io/console/user/settings
# (Make sure to add a small balance to your RunPod account first — a single
# A100 run for 10–15 min is around $0.40, but RunPod requires a minimum
# top-up of $10.)
RUNPOD_API_KEY = "rpa_REPLACE_ME"

# The base URL of the workshop's storage pod (your workshop host gives you
# this — it looks like "https://abc123-8000.proxy.runpod.net").
# Falls back to a default below if the host has set one.
STORAGE_POD_URL = "https://REPLACE_ME-8000.proxy.runpod.net"

# ---------------------------------------------------------------------------
# Sane defaults — usually don't need to edit anything below this line.
# ---------------------------------------------------------------------------

# What to call the GPU pod that gets spun up under your account.
GPU_POD_NAME = "zero-to-llm-attendee"

# Which GPU type to request. "NVIDIA A100 80GB PCIe" is plenty for a tiny
# demo model and is generally available across RunPod regions. The launcher
# falls back to "NVIDIA A100-SXM4-80GB" if PCIe is out of stock.
GPU_TYPE_PREFERENCE = [
    "NVIDIA A100 80GB PCIe",
    "NVIDIA A100-SXM4-80GB",
    "NVIDIA H100 80GB HBM3",
    "NVIDIA H100 PCIe",
]

# RunPod PyTorch image — has CUDA, PyTorch, JupyterLab pre-installed.
GPU_POD_IMAGE = "runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04"

# Container disk in GB (nanochat venv + checkpoints + tokenized data).
GPU_POD_DISK_GB = 60

# This is the workshop repo URL the pod will clone. If you fork this repo,
# point this at your fork.
WORKSHOP_REPO_URL = "https://github.com/ancelik/zero-to-llm.git"

# Which SEC sections to train on by default. Override in the notebook if
# you want a different mix. Options: "all", "business", "market_risk",
# "mda", "risk_factors".
DEFAULT_DATA_SCOPE = "all"
