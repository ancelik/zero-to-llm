"""
Attendee launcher (script form).

What this does:
  1. Reads your RunPod API key + workshop's storage pod URL from
     attendee/config.py.
  2. Spins up a 1× A100 80GB GPU pod under YOUR RunPod account, using
     RunPod's PyTorch+JupyterLab image.
  3. Sets a startup command on the pod that:
        - clones the workshop repo + nanochat
        - downloads the SEC parquets from the storage pod
        - installs nanochat into a venv
        - leaves JupyterLab running for you to open
  4. Prints the JupyterLab URL once the pod is healthy.

You'll then open that URL in your browser, navigate to
`zero-to-llm/pod/02_train_workshop.ipynb`, and run cells.

If you'd rather use a notebook for this launch step, run
`attendee/launch_pod.ipynb` — it's the same logic, cell-by-cell.

Usage:
    python attendee/launch_pod.py
"""

import os
import sys
import time
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "attendee"))

try:
    import config
except ImportError:
    print("ERROR: attendee/config.py not found.", file=sys.stderr)
    print("       Copy attendee/config.example.py -> attendee/config.py and fill it in.",
          file=sys.stderr)
    sys.exit(1)

try:
    import runpod
except ImportError:
    print("ERROR: the `runpod` package is not installed.", file=sys.stderr)
    print("       Run:  pip install -r attendee/requirements_local.txt", file=sys.stderr)
    sys.exit(1)


def validate_config():
    if not config.RUNPOD_API_KEY or "REPLACE_ME" in config.RUNPOD_API_KEY:
        print("ERROR: please set RUNPOD_API_KEY in attendee/config.py", file=sys.stderr)
        sys.exit(2)
    if not config.STORAGE_POD_URL or "REPLACE_ME" in config.STORAGE_POD_URL:
        print("ERROR: please set STORAGE_POD_URL in attendee/config.py", file=sys.stderr)
        print("       Your workshop host should have given you this URL.", file=sys.stderr)
        sys.exit(2)


def pick_available_gpu(preferences):
    """Return the first preferred GPU type that has stock available."""
    available = {gpu["id"]: gpu for gpu in runpod.get_gpus()}
    for name in preferences:
        if name in available:
            return name
    raise RuntimeError(
        f"None of the preferred GPU types are listed: {preferences}. "
        f"Available IDs: {sorted(available.keys())}"
    )


def build_startup_command():
    """The bash command run as the pod's docker entry.

    Clones the workshop repo, then hands off to pod/startup.sh which does
    the rest (nanochat install, data download, etc). The script logs to
    /workspace/startup.log; the training notebook waits for "Setup complete".

    Ends with `sleep infinity` so the container stays alive for JupyterLab
    (which is started in the background by the runpod/pytorch image's
    default entrypoint).
    """
    return (
        "bash -lc '"
        "set -e; "
        "mkdir -p /workspace && cd /workspace; "
        f"git clone {config.WORKSHOP_REPO_URL} /workspace/zero-to-llm || true; "
        "bash /workspace/zero-to-llm/pod/startup.sh || echo SETUP_FAILED >> /workspace/startup.log; "
        "sleep infinity"
        "'"
    )


def wait_for_jupyter(pod_id: str, jupyter_url: str, timeout_s: int = 600):
    """Poll the JupyterLab URL until it returns 200/302 (image is ready)."""
    import urllib.request
    import urllib.error
    print(f"  Polling {jupyter_url} ...")
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            req = urllib.request.Request(jupyter_url, method="HEAD")
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 302):
                    return True
        except urllib.error.HTTPError as e:
            if e.code in (200, 302, 401, 403):  # auth-required is fine, server is up
                return True
        except Exception:
            pass
        time.sleep(10)
        print(f"    ... still booting ({int(time.time() - start)}s)")
    return False


def main():
    validate_config()
    runpod.api_key = config.RUNPOD_API_KEY

    print("Step 1: Pick an available GPU type from your preference list")
    gpu_type = pick_available_gpu(config.GPU_TYPE_PREFERENCE)
    print(f"  Using: {gpu_type}")

    print("\nStep 2: Create the GPU pod under your account")
    pod = runpod.create_pod(
        name=config.GPU_POD_NAME,
        image_name=config.GPU_POD_IMAGE,
        gpu_type_id=gpu_type,
        gpu_count=1,
        cloud_type="ALL",
        container_disk_in_gb=config.GPU_POD_DISK_GB,
        ports="8888/http,22/tcp",  # 8888 = JupyterLab, 22 = SSH
        docker_args=build_startup_command(),
        support_public_ip=True,
        start_ssh=True,
        env={
            "JUPYTER_TOKEN": "",                                # disable token; proxy URL is private
            "JUPYTER_PASSWORD": "",
            "STORAGE_POD_URL": config.STORAGE_POD_URL,          # consumed by pod/startup.sh
            "DATA_SCOPE": config.DEFAULT_DATA_SCOPE,
            "WORKSHOP_REPO_URL": config.WORKSHOP_REPO_URL,
        },
    )
    pod_id = pod["id"]
    print(f"  Pod created: id={pod_id}")
    jupyter_url = f"https://{pod_id}-8888.proxy.runpod.net/lab"

    print("\nStep 3: Wait for JupyterLab to be reachable")
    print( "  (the pod is also git-cloning + downloading data + installing nanochat in")
    print( "   the background; JupyterLab itself is up much sooner. You can start using")
    print( "   the URL as soon as it loads, but the FIRST cells of the training notebook")
    print( "   wait for /workspace/startup.log to print 'Setup complete'.)")
    if not wait_for_jupyter(pod_id, jupyter_url):
        print("WARNING: JupyterLab didn't respond within 10 minutes.", file=sys.stderr)
        print( "         Check the RunPod console for pod status:", file=sys.stderr)
        print(f"         https://www.runpod.io/console/pods/{pod_id}", file=sys.stderr)

    print()
    print("=" * 70)
    print("  POD IS READY")
    print("=" * 70)
    print(f"  JupyterLab URL: {jupyter_url}")
    print()
    print("  Next steps:")
    print("   1. Open the URL above in your browser.")
    print("   2. In JupyterLab, navigate to:")
    print("        zero-to-llm/pod/02_train_workshop.ipynb")
    print("   3. Run the cells top to bottom.")
    print("   4. When done, terminate the pod from the RunPod console:")
    print(f"        https://www.runpod.io/console/pods/{pod_id}")
    print("      (terminating prevents further charges).")
    print()
    print(f"  Pod ID (save this in case you need it): {pod_id}")


if __name__ == "__main__":
    main()
