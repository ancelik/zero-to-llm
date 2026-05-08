"""
Pod-side helper. Stages the SEC parquets we downloaded from the storage
pod into the directory layout that nanochat expects.

nanochat reads pretraining data from `~/.cache/nanochat/base_data_climbmix/`
as a sequence of `shard_NNNNN.parquet` files, each with a `text` column.
The last shard is treated as validation; the rest are training.

The four SEC parquets already have a `text` column (alongside ticker, cik,
form_type, etc.), so we mostly just need to:
  1. Pick which sections to include based on --scope.
  2. Concatenate / split into train shards + 1 val shard.
  3. Drop columns we don't need so nanochat doesn't fall over.
  4. Write `shard_NNNNN.parquet` files in the expected directory.

Usage (from inside the pod, with the nanochat venv activated):
    python /workspace/zero-to-llm/pod/prep_sec_data.py --scope all
    python /workspace/zero-to-llm/pod/prep_sec_data.py --scope risk_factors

Scope values:
    all           -> all four sections
    business      -> Item 1, Business
    market_risk   -> Item 7A
    mda           -> Item 7, MD&A
    risk_factors  -> Item 1A, Risk Factors
"""

import argparse
import os
import pathlib
import sys

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

SOURCE_DIR = pathlib.Path("/workspace/sec_data")
SCOPE_FILES = {
    "business":     ["business_2025_2026.parquet"],
    "market_risk":  ["market_risk_2025_2026.parquet"],
    "mda":          ["mda_2025_2026.parquet"],
    "risk_factors": ["risk_factors_2025_2026.parquet"],
    "all": [
        "business_2025_2026.parquet",
        "market_risk_2025_2026.parquet",
        "mda_2025_2026.parquet",
        "risk_factors_2025_2026.parquet",
    ],
}

# nanochat reads from this dir (see nanochat/dataset.py)
NANOCHAT_BASE_DIR = pathlib.Path(os.environ.get("NANOCHAT_BASE_DIR", pathlib.Path.home() / ".cache" / "nanochat"))
TARGET_DIR = NANOCHAT_BASE_DIR / "base_data_climbmix"

# How many train shards to produce. The last shard goes to val. We want a
# few shards so the dataloader can stripe across them in DDP, but we're
# single-GPU + 10-min training, so 4 shards (3 train + 1 val) is plenty.
NUM_SHARDS = 4


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scope", default="all", choices=list(SCOPE_FILES.keys()))
    ap.add_argument("--target-dir", default=str(TARGET_DIR))
    ap.add_argument("--num-shards", type=int, default=NUM_SHARDS)
    args = ap.parse_args()

    target_dir = pathlib.Path(args.target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    files = SCOPE_FILES[args.scope]
    print(f"Scope '{args.scope}' -> {len(files)} source parquet(s)")

    # Read all selected parquets into one pandas frame, keeping only `text`.
    frames = []
    for fname in files:
        path = SOURCE_DIR / fname
        if not path.exists():
            print(f"ERROR: missing {path}", file=sys.stderr)
            sys.exit(1)
        df = pd.read_parquet(path, columns=["text"])
        # Drop empty / tiny rows; they hurt the tokenizer and waste tokens.
        df = df[df["text"].str.len() > 200].reset_index(drop=True)
        print(f"  {fname}: {len(df):,} rows after filtering empties")
        frames.append(df)
    big = pd.concat(frames, ignore_index=True)
    print(f"Total docs after concat: {len(big):,}")

    # Shuffle so train/val isn't biased to one filing type or filing date
    big = big.sample(frac=1.0, random_state=42).reset_index(drop=True)

    # Slice into shards. The final shard is val.
    n = len(big)
    shard_size = (n + args.num_shards - 1) // args.num_shards
    print(f"Writing {args.num_shards} shards (~{shard_size:,} docs each) to {target_dir}")

    # Wipe any previous shards we wrote so there are no leftovers
    for old in target_dir.glob("shard_*.parquet"):
        old.unlink()

    for i in range(args.num_shards):
        chunk = big.iloc[i * shard_size:(i + 1) * shard_size]
        if len(chunk) == 0:
            continue
        out_path = target_dir / f"shard_{i:05d}.parquet"
        pq.write_table(pa.Table.from_pandas(chunk[["text"]]), out_path)
        size_mb = out_path.stat().st_size / 1e6
        print(f"  wrote {out_path.name}  rows={len(chunk):,}  size={size_mb:.1f} MB")

    print("Done.")


if __name__ == "__main__":
    main()
