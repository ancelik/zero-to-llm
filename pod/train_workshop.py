"""
Pod-side, run inside the GPU pod from a JupyterLab terminal.

Drives the full mini-nanochat pipeline against the SEC parquets:
    1. Wait for `/workspace/startup.log` to say "Setup complete"
       (the launcher's pod startup script is still installing nanochat
       and downloading data when JupyterLab first comes up).
    2. (Optional) Re-stage SEC parquets if you change --scope.
    3. Train a custom BPE tokenizer on the SEC text (vocab 4096).
    4. Pretrain a tiny GPT (depth 4, ~5–8M params) for ~5–7 minutes
       on a single A100 80GB.
    5. Sample some completions to show the model has learned SEC-flavored
       text patterns.

For the chat REPL, run pod/chat.py separately (or use pod/03_chat.ipynb).

Usage (from /workspace/nanochat with the venv activated — the launcher does
this for you when it runs the startup command, but you can re-activate
manually with `source /workspace/nanochat/.venv/bin/activate`):

    python /workspace/zero-to-llm/pod/train_workshop.py \
        --scope all \
        --depth 4 \
        --num-iterations 400 \
        --vocab-size 4096
"""

import argparse
import os
import pathlib
import subprocess
import sys
import time


NANOCHAT_DIR = pathlib.Path("/workspace/nanochat")
WORKSHOP_DIR = pathlib.Path("/workspace/zero-to-llm")
STARTUP_LOG = pathlib.Path("/workspace/startup.log")


def wait_for_setup_complete(timeout_s: int = 900):
    """Block until the pod's startup script has finished installing nanochat."""
    print("Waiting for pod setup to finish (nanochat install + data download)...")
    start = time.time()
    while time.time() - start < timeout_s:
        if STARTUP_LOG.exists() and "Setup complete" in STARTUP_LOG.read_text():
            print(f"  Setup complete ({int(time.time() - start)}s).")
            return
        time.sleep(5)
        try:
            tail = STARTUP_LOG.read_text().splitlines()[-1] if STARTUP_LOG.exists() else "(no log yet)"
        except Exception:
            tail = "(reading log failed)"
        print(f"  ... still installing. last line: {tail}")
    raise TimeoutError("Pod setup didn't finish within %d s. Check /workspace/startup.log" % timeout_s)


def run(cmd, cwd=None, env=None):
    """Run a subprocess, streaming stdout to the parent. Raises on nonzero exit."""
    print(f"\n$ {' '.join(cmd)}\n")
    proc = subprocess.Popen(cmd, cwd=cwd, env=env, stdout=sys.stdout, stderr=sys.stderr)
    rc = proc.wait()
    if rc != 0:
        raise SystemExit(f"Command failed (rc={rc}): {' '.join(cmd)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="all",
                    choices=["all", "business", "market_risk", "mda", "risk_factors"],
                    help="Which SEC section(s) to train on.")
    ap.add_argument("--restage-data", action="store_true",
                    help="Re-run prep_sec_data.py before training (use if --scope changed).")
    ap.add_argument("--depth", type=int, default=4,
                    help="Transformer depth (4 -> ~5M params, 6 -> ~14M, 8 -> ~30M).")
    ap.add_argument("--max-seq-len", type=int, default=1024)
    ap.add_argument("--device-batch-size", type=int, default=8)
    ap.add_argument("--total-batch-size", type=int, default=32768,
                    help="Total batch size in tokens.")
    ap.add_argument("--num-iterations", type=int, default=400,
                    help="Optimizer steps. ~400 fits in ~5–7 min on a single A100.")
    ap.add_argument("--vocab-size", type=int, default=4096,
                    help="Custom BPE vocab size. Smaller -> faster tokenizer, faster model.")
    ap.add_argument("--max-tokenizer-chars", type=int, default=20_000_000,
                    help="Cap on characters used to train the tokenizer. 20 M ~= 30 s.")
    ap.add_argument("--eval-tokens", type=int, default=4096)
    ap.add_argument("--eval-every", type=int, default=100)
    ap.add_argument("--sample-every", type=int, default=100)
    args = ap.parse_args()

    wait_for_setup_complete()

    # Activate-style env: prepend the nanochat venv's bin to PATH and set
    # the venv's site-packages so `python` and `python -m` resolve correctly.
    venv = NANOCHAT_DIR / ".venv"
    env = os.environ.copy()
    env["PATH"] = f"{venv}/bin:" + env.get("PATH", "")
    env["VIRTUAL_ENV"] = str(venv)
    env["NANOCHAT_BASE_DIR"] = env.get("NANOCHAT_BASE_DIR", str(pathlib.Path.home() / ".cache" / "nanochat"))
    env["OMP_NUM_THREADS"] = "1"

    # Optional re-stage if attendee changed --scope after first launch.
    if args.restage_data:
        run(
            [str(venv / "bin/python"), str(WORKSHOP_DIR / "pod/prep_sec_data.py"),
             "--scope", args.scope],
            env=env,
        )

    # ------------------------------------------------------------------
    # Step 1: train the tokenizer on SEC text.
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("Step 1/3: Train custom BPE tokenizer on SEC text")
    print("=" * 70)
    run(
        [
            str(venv / "bin/python"), "-m", "scripts.tok_train",
            "--max-chars", str(args.max_tokenizer_chars),
            "--vocab-size", str(args.vocab_size),
        ],
        cwd=str(NANOCHAT_DIR), env=env,
    )

    # ------------------------------------------------------------------
    # Step 2: pretrain a tiny GPT
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("Step 2/3: Pretrain tiny GPT on SEC text")
    print("=" * 70)
    run(
        [
            str(venv / "bin/python"), "-m", "scripts.base_train",
            "--depth", str(args.depth),
            "--max-seq-len", str(args.max_seq_len),
            "--device-batch-size", str(args.device_batch_size),
            "--total-batch-size", str(args.total_batch_size),
            "--num-iterations", str(args.num_iterations),
            "--eval-tokens", str(args.eval_tokens),
            "--eval-every", str(args.eval_every),
            "--sample-every", str(args.sample_every),
            "--core-metric-every", "-1",  # CORE eval is slow & not meaningful for tiny SEC model
            "--run", "dummy",             # disable wandb
        ],
        cwd=str(NANOCHAT_DIR), env=env,
    )

    # ------------------------------------------------------------------
    # Step 3: a few sample generations from the just-trained base model.
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("Step 3/3: Sample generations from your model")
    print("=" * 70)
    run(
        [str(venv / "bin/python"), str(WORKSHOP_DIR / "pod/sample_generations.py")],
        cwd=str(NANOCHAT_DIR), env=env,
    )

    print()
    print("=" * 70)
    print("  TRAINING COMPLETE.")
    print("=" * 70)
    print()
    print("  To chat interactively, run:")
    print(f"      python {WORKSHOP_DIR}/pod/chat.py")
    print("  ...or open pod/03_chat.ipynb in JupyterLab.")


if __name__ == "__main__":
    main()
