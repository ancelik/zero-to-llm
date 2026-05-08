"""
Host-side, run once before the workshop.

Spins up a small RunPod CPU pod that serves the four SEC parquet files over
HTTP, then uploads the parquets to it via SCP. Attendee GPU pods will
`wget` from this pod when they boot.

Usage:
    1. Copy host/config.example.py -> host/config.py and fill in your
       RunPod API key.
    2. Run:
           python host/deploy_storage_pod.py
    3. Note the printed URL — paste it into attendee/config.example.py as
       STORAGE_POD_URL (and commit), or share it with attendees.

Cost: ~$0.04/hour for the CPU pod. Terminate it via the RunPod console
when the workshop is over.

Cross-platform notes:
- Requires `scp` and `ssh-keygen` on PATH. Mac/Linux: built-in. Windows 10+:
  built-in via the OpenSSH Client optional feature (enabled by default
  since Win10 1803).
"""

import os
import sys
import subprocess
import pathlib
import time

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))

try:
    import config
except ImportError:
    print("ERROR: host/config.py not found.", file=sys.stderr)
    print("       Copy host/config.example.py -> host/config.py and fill it in.", file=sys.stderr)
    sys.exit(1)

try:
    import runpod
except ImportError:
    print("ERROR: the `runpod` package is not installed.", file=sys.stderr)
    print("       Run:  pip install runpod", file=sys.stderr)
    sys.exit(1)

DATA_DIR = REPO_ROOT / "data" / "filings-2025-2026"
PARQUET_FILES = [
    "business_2025_2026.parquet",
    "market_risk_2025_2026.parquet",
    "mda_2025_2026.parquet",
    "risk_factors_2025_2026.parquet",
]

# Slim Python image. Has http.server in stdlib. ~50 MB.
IMAGE = "python:3.11-slim"
HTTP_PORT = 8000

# Start http.server immediately on /data (which is initially empty); SCP
# uploads from upload_data.py populate it.
DOCKER_ARGS = (
    "/bin/bash -lc '"
    "mkdir -p /data && "
    "apt-get update -qq && apt-get install -y -qq openssh-server && "
    "mkdir -p /run/sshd && "
    "service ssh start && "
    "cd /data && exec python3 -m http.server " + str(HTTP_PORT) +
    "'"
)


def ensure_ssh_key() -> str:
    """Make sure ~/.ssh/id_ed25519 exists, return the matching public key."""
    home = pathlib.Path.home()
    priv = home / ".ssh" / "id_ed25519"
    pub = home / ".ssh" / "id_ed25519.pub"
    if not priv.exists():
        print(f"  No SSH key at {priv}; generating one (ed25519, no passphrase) ...")
        priv.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-f", str(priv), "-N", "", "-q"],
            check=True,
        )
    return pub.read_text().strip()


def register_ssh_pubkey(pubkey: str):
    print("  Registering SSH public key with RunPod account ...")
    runpod.update_user_settings(pubkey=pubkey)


def find_existing_pod():
    for pod in runpod.get_pods():
        if pod.get("name") == config.STORAGE_POD_NAME:
            return pod
    return None


def wait_for_runtime(pod_id: str, timeout_s: int = 360):
    """Poll until pod runtime info has port mappings populated."""
    start = time.time()
    while time.time() - start < timeout_s:
        info = runpod.get_pod(pod_id)
        rt = info.get("runtime") if info else None
        if rt and rt.get("ports"):
            return info
        time.sleep(5)
        print(f"    ... still booting ({int(time.time() - start)}s)")
    raise TimeoutError("Pod did not come up within %d seconds." % timeout_s)


def public_endpoint(pod_info: dict, private_port: int):
    """Return (ip, port) tuple for a TCP port, or (None, None) if proxy-only."""
    for p in pod_info.get("runtime", {}).get("ports", []):
        if p.get("privatePort") == private_port and p.get("isIpPublic"):
            return p.get("ip"), p.get("publicPort")
    return None, None


def main():
    runpod.api_key = config.RUNPOD_API_KEY

    print("Step 1: Ensure local SSH key + register with RunPod")
    pubkey = ensure_ssh_key()
    register_ssh_pubkey(pubkey)

    print("\nStep 2: Look for an existing storage pod")
    pod = find_existing_pod()
    if pod:
        print(f"  Found existing pod {pod['id']} (status={pod.get('desiredStatus')}).")
        print( "  Reusing it. Terminate via RunPod console if you want a fresh deploy.")
        pod_id = pod["id"]
    else:
        print("  Creating new CPU storage pod ...")
        created = runpod.create_pod(
            name=config.STORAGE_POD_NAME,
            image_name=IMAGE,
            instance_id=config.STORAGE_POD_CPU_INSTANCE_ID,
            container_disk_in_gb=config.STORAGE_POD_DISK_GB,
            ports=f"{HTTP_PORT}/http,22/tcp",
            docker_args=DOCKER_ARGS,
            support_public_ip=True,
            start_ssh=True,
        )
        pod_id = created["id"]
        print(f"  Created pod {pod_id}")

    print("\nStep 3: Wait for pod runtime info (HTTP proxy + SSH port)")
    info = wait_for_runtime(pod_id)
    ssh_ip, ssh_port = public_endpoint(info, 22)
    if not ssh_ip:
        print("ERROR: pod has no public SSH endpoint. RunPod may be out of capacity", file=sys.stderr)
        print("       on machines that expose public TCP ports. Try a different region.", file=sys.stderr)
        sys.exit(3)
    proxy_url = f"https://{pod_id}-{HTTP_PORT}.proxy.runpod.net"
    print(f"  HTTP proxy URL : {proxy_url}")
    print(f"  SSH endpoint   : root@{ssh_ip}:{ssh_port}")

    print("\nStep 4: Wait for SSH to accept connections (apt-get install in container takes ~30s)")
    for attempt in range(36):
        rc = subprocess.run(
            [
                "ssh", "-p", str(ssh_port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ConnectTimeout=5",
                "-o", "LogLevel=ERROR",
                f"root@{ssh_ip}",
                "true",
            ],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode
        if rc == 0:
            print(f"  SSH up after {(attempt + 1) * 5}s")
            break
        time.sleep(5)
        print(f"    ... waiting for ssh ({(attempt + 1) * 5}s)")
    else:
        print("ERROR: ssh never came up. Check the pod logs in the RunPod console.", file=sys.stderr)
        sys.exit(4)

    print("\nStep 5: SCP parquets up to /data on the pod")
    for fname in PARQUET_FILES:
        local = DATA_DIR / fname
        if not local.exists():
            print(f"ERROR: missing {local}. Cannot upload.", file=sys.stderr)
            sys.exit(5)
        print(f"  Uploading {fname} ({local.stat().st_size / 1e6:.1f} MB) ...")
        subprocess.run(
            [
                "scp", "-P", str(ssh_port),
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "LogLevel=ERROR",
                str(local),
                f"root@{ssh_ip}:/data/{fname}",
            ],
            check=True,
        )

    print("\nStep 6: Verify parquets are reachable via HTTP")
    import urllib.request
    for fname in PARQUET_FILES:
        url = f"{proxy_url}/{fname}"
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=15) as resp:
                size_mb = int(resp.headers.get("Content-Length", "0")) / 1e6
            print(f"  OK    {url}   ({size_mb:.1f} MB)")
        except Exception as exc:
            print(f"  FAIL  {url}   ({exc})", file=sys.stderr)

    print()
    print("=" * 70)
    print("  STORAGE POD READY")
    print("=" * 70)
    print(f"  Public base URL: {proxy_url}")
    print()
    print("  Paste this URL into attendee/config.example.py as STORAGE_POD_URL.")
    print("  When the workshop is over, terminate the pod via the RunPod console:")
    print(f"      https://www.runpod.io/console/pods")
    print()


if __name__ == "__main__":
    main()
