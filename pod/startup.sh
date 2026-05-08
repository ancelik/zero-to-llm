#!/usr/bin/env bash
# Pod-side startup script. Runs once when the GPU pod first boots,
# kicked off by the launcher's docker_args.
#
# Reads these env vars (set by the launcher via `runpod.create_pod(env=...)`):
#   STORAGE_POD_URL  - public base URL of the workshop's storage pod
#   DATA_SCOPE       - "all" | "business" | "market_risk" | "mda" | "risk_factors"
#
# Logs everything to /workspace/startup.log. The training notebook waits
# for the line "Setup complete" to appear in that log before proceeding.

set -e
exec > /workspace/startup.log 2>&1

ts() { date '+[%Y-%m-%d %H:%M:%S]'; }

echo "$(ts) Pod startup script starting."
echo "$(ts) STORAGE_POD_URL=${STORAGE_POD_URL:-(unset)}"
echo "$(ts) DATA_SCOPE=${DATA_SCOPE:-all}"

if [ -z "$STORAGE_POD_URL" ]; then
    echo "$(ts) ERROR: STORAGE_POD_URL env var is required."
    exit 2
fi

cd /workspace

echo "$(ts) Cloning nanochat ..."
if [ ! -d /workspace/nanochat ]; then
    git clone https://github.com/karpathy/nanochat.git /workspace/nanochat
fi

echo "$(ts) Downloading SEC parquets from storage pod ..."
mkdir -p /workspace/sec_data
for f in business_2025_2026.parquet market_risk_2025_2026.parquet \
         mda_2025_2026.parquet risk_factors_2025_2026.parquet; do
    if [ -f "/workspace/sec_data/$f" ]; then
        echo "$(ts)   $f already present, skipping."
    else
        curl -fsSL "$STORAGE_POD_URL/$f" -o "/workspace/sec_data/$f"
        size=$(stat -c%s "/workspace/sec_data/$f" 2>/dev/null || stat -f%z "/workspace/sec_data/$f")
        echo "$(ts)   fetched $f (${size} bytes)"
    fi
done

echo "$(ts) Installing uv (Python package manager) ..."
if ! command -v uv >/dev/null 2>&1; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "$(ts) Installing nanochat deps (this is the slow step, ~2 min) ..."
cd /workspace/nanochat
uv venv
uv sync --extra gpu

echo "$(ts) Staging SEC parquets into nanochat data dir ..."
source /workspace/nanochat/.venv/bin/activate
python /workspace/zero-to-llm/pod/prep_sec_data.py --scope "${DATA_SCOPE:-all}"

echo "$(ts) Setup complete. Open zero-to-llm/pod/02_train_workshop.ipynb to begin."
