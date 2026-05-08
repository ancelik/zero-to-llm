"""
Host config template.

Copy to `host/config.py` and fill in. `host/config.py` is gitignored.
You only need to do this once, before the workshop.
"""

# Your personal RunPod API key (NOT shared with attendees).
# Find/create one at: https://www.runpod.io/console/user/settings
RUNPOD_API_KEY = "rpa_REPLACE_ME"

# Name to give the storage pod when it appears in your RunPod console.
STORAGE_POD_NAME = "zero-to-llm-storage"

# Container disk size for the storage pod, in GB. The four SEC parquets are
# ~1 GB total, so 10 GB is plenty (RunPod's minimum for a CPU pod).
STORAGE_POD_DISK_GB = 10

# Which RunPod CPU instance type to use for the storage pod. The cheapest
# CPU option ($0.04/hr-ish) is fine — this is just an HTTP file server.
# You can list options with `runpod.get_gpus()` (CPU types are listed too in
# the GraphQL API; the SDK accepts an `instance_id` like "cpu3c-2-4").
STORAGE_POD_CPU_INSTANCE_ID = "cpu3c-2-4"
