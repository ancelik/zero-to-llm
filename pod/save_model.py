"""
Pod-side. Bundles the trained model + tokenizer into a single tarball
under /workspace/sec_llm.tar.gz so you can download it from JupyterLab
(File browser → right-click sec_llm.tar.gz → Download).

What's inside:
    base_checkpoints/<model_tag>/<latest_step>/   — model_*.pt + meta_*.json
    tokenizer/                                    — your custom BPE tokenizer

Usage:
    python /workspace/zero-to-llm/pod/save_model.py
"""

import os
import pathlib
import shutil
import tarfile

NANOCHAT_BASE_DIR = pathlib.Path(os.environ.get("NANOCHAT_BASE_DIR",
                                                pathlib.Path.home() / ".cache" / "nanochat"))
OUT_PATH = pathlib.Path("/workspace/sec_llm.tar.gz")


def _latest_run(checkpoints_dir: pathlib.Path):
    """Returns (model_tag_dir, latest_model_pt, latest_meta_json) or None."""
    if not checkpoints_dir.exists():
        return None
    tags = [d for d in checkpoints_dir.iterdir() if d.is_dir()]
    if not tags:
        return None
    # Pick the most recently modified (covers any naming convention)
    tag_dir = max(tags, key=lambda d: d.stat().st_mtime)
    pts = sorted(tag_dir.glob("model_*.pt"))
    metas = sorted(tag_dir.glob("meta_*.json"))
    if not pts or not metas:
        return None
    return tag_dir, pts[-1], metas[-1]


def main():
    base_ckpts = NANOCHAT_BASE_DIR / "base_checkpoints"
    found = _latest_run(base_ckpts)
    if found is None:
        raise SystemExit(f"No base checkpoints found under {base_ckpts}. Run training first.")
    tag_dir, pt_path, meta_path = found
    print(f"  Latest base checkpoint : {pt_path.relative_to(NANOCHAT_BASE_DIR)}  ({pt_path.stat().st_size / 1e6:.1f} MB)")

    tok_dir = NANOCHAT_BASE_DIR / "tokenizer"
    if not tok_dir.exists():
        raise SystemExit(f"Tokenizer not found at {tok_dir}.")
    print(f"  Tokenizer dir          : {tok_dir.relative_to(NANOCHAT_BASE_DIR)}")

    print(f"  Bundling -> {OUT_PATH} ...")
    with tarfile.open(OUT_PATH, "w:gz") as tar:
        # Add the model tag dir (just the latest step's pt + meta, plus anything else in there).
        tar.add(tag_dir, arcname=f"base_checkpoints/{tag_dir.name}")
        tar.add(tok_dir, arcname="tokenizer")

    size_mb = OUT_PATH.stat().st_size / 1e6
    print()
    print("=" * 70)
    print(f"  Bundle ready: {OUT_PATH}  ({size_mb:.1f} MB)")
    print("=" * 70)
    print()
    print("  In JupyterLab, navigate to /workspace/, right-click sec_llm.tar.gz,")
    print("  and choose 'Download' to save it to your laptop.")


if __name__ == "__main__":
    main()
