"""
Sanity-check the local environment before running the launcher.

Verifies:
  - Python >= 3.10
  - `runpod` package installed
  - attendee/config.py exists and has been edited (no REPLACE_ME)
  - the RunPod API key is valid (makes a small API call)
  - the storage pod URL responds (HEAD request to one parquet)

Run from the repo root with the venv activated:
    python setup/verify.py
"""

import sys
import pathlib
import urllib.request
import urllib.error

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "attendee"))

PARQUETS = [
    "business_2025_2026.parquet",
    "market_risk_2025_2026.parquet",
    "mda_2025_2026.parquet",
    "risk_factors_2025_2026.parquet",
]


def fail(msg, hint=None):
    print(f"  ✗ {msg}")
    if hint:
        print(f"      → {hint}")
    sys.exit(1)


def main():
    print("Checking Python version ...")
    if sys.version_info < (3, 10):
        fail(f"Python 3.10+ required (you have {sys.version_info.major}.{sys.version_info.minor}).",
             "Install Python 3.10+ from https://www.python.org/downloads/")
    print(f"  ✓ Python {sys.version_info.major}.{sys.version_info.minor}")

    print("Checking runpod SDK ...")
    try:
        import runpod
    except ImportError:
        fail("`runpod` package not installed.",
             "Run: pip install -r attendee/requirements_local.txt   (or re-run setup/setup.sh)")
    print(f"  ✓ runpod {getattr(runpod, '__version__', '?')}")

    print("Checking attendee/config.py ...")
    cfg_path = REPO_ROOT / "attendee" / "config.py"
    if not cfg_path.exists():
        fail("attendee/config.py not found.",
             "Copy attendee/config.example.py -> attendee/config.py and fill it in.")
    try:
        import config  # type: ignore
    except Exception as e:
        fail(f"could not import attendee/config.py: {e}")
    if "REPLACE_ME" in config.RUNPOD_API_KEY:
        fail("RUNPOD_API_KEY still set to placeholder.",
             "Edit attendee/config.py and paste your real RunPod API key.")
    if "REPLACE_ME" in config.STORAGE_POD_URL:
        fail("STORAGE_POD_URL still set to placeholder.",
             "Your workshop host should give you the storage pod URL. Paste it into attendee/config.py.")
    print(f"  ✓ config.py looks filled in")

    print("Checking RunPod API key ...")
    runpod.api_key = config.RUNPOD_API_KEY
    try:
        user = runpod.get_user()
    except Exception as e:
        fail(f"RunPod API key rejected: {e}",
             "Double-check the key at https://www.runpod.io/console/user/settings")
    if not user:
        fail("RunPod API responded but didn't return a user.")
    email = user.get("email", "(unknown)")
    print(f"  ✓ logged in as {email}")

    print("Checking storage pod URL ...")
    try:
        req = urllib.request.Request(f"{config.STORAGE_POD_URL}/{PARQUETS[0]}", method="HEAD")
        with urllib.request.urlopen(req, timeout=15) as resp:
            length = int(resp.headers.get("Content-Length", "0"))
        print(f"  ✓ {config.STORAGE_POD_URL}/{PARQUETS[0]} reachable ({length / 1e6:.1f} MB)")
    except Exception as e:
        fail(f"could not reach the storage pod: {e}",
             "Verify with your workshop host that STORAGE_POD_URL is correct and the pod is running.")

    print()
    print("✓ All checks passed. You're ready to launch.")
    print()
    print("Next: python attendee/launch_pod.py")


if __name__ == "__main__":
    main()
