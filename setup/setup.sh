#!/usr/bin/env bash
# Cross-platform setup for Mac and Linux. Windows users: use setup.ps1.
#
# What this does:
#   1. Verifies Python >= 3.10 is installed.
#   2. Creates a local virtualenv in .venv/ at the repo root.
#   3. Installs the local-only deps (RunPod SDK + requests).
#   4. Copies attendee/config.example.py -> attendee/config.py if it doesn't exist.
#   5. Reminds you to fill in your RunPod API key.

set -e

# Resolve repo root (parent of the dir containing this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

echo "=== zero-to-llm local setup ==="
echo "Repo root: $REPO_ROOT"

# 1. Find a Python >= 3.10
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        version=$("$candidate" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
            PYTHON="$candidate"
            echo "Found Python: $candidate (version $version)"
            break
        fi
    fi
done
if [ -z "$PYTHON" ]; then
    echo "ERROR: no Python >= 3.10 found on PATH." >&2
    echo "       Install Python 3.10+ from https://www.python.org/downloads/" >&2
    echo "       Mac users: 'brew install python@3.12' is fine." >&2
    exit 1
fi

# 2. Create venv
if [ ! -d ".venv" ]; then
    echo "Creating virtualenv at .venv/ ..."
    "$PYTHON" -m venv .venv
else
    echo "Reusing existing .venv/"
fi

# 3. Install local deps
echo "Installing local deps ..."
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r attendee/requirements_local.txt

# 4. Copy config template if needed
if [ ! -f "attendee/config.py" ]; then
    cp attendee/config.example.py attendee/config.py
    echo "Created attendee/config.py from the template."
fi

# 5. Reminder
echo
echo "==============================================================="
echo "  Setup complete."
echo "==============================================================="
echo
echo "  Next steps:"
echo "  1. Edit attendee/config.py and set:"
echo "       - RUNPOD_API_KEY  (from https://www.runpod.io/console/user/settings)"
echo "       - STORAGE_POD_URL (your workshop host gives you this)"
echo "  2. Activate the venv:    source .venv/bin/activate"
echo "  3. Verify your config:   python setup/verify.py"
echo "  4. Launch the GPU pod:   python attendee/launch_pod.py"
echo "                           (or open attendee/launch_pod.ipynb)"
echo
