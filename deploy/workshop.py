"""
Workshop backend — lives on the droplet, imported by the Jupyter kernel.

Two jobs:

1. BACKUP. Training happens on RunPod (a CPU would take forever). But once a run
   finishes, we copy the trained model, its tokenizer and the embeddings back to
   the droplet. They are small — a few tens of MB. From then on the demo can run
   without RunPod at all: if pods are sold out, the API is down, or a cell dies
   on stage, we still have a real model and real embeddings to show.

2. FAST CHAT. The model is ~5M parameters. Generating a couple of hundred tokens
   on the droplet's CPU takes well under a second, and needs no SSH round-trip.
   So chat is served locally from the saved checkpoint — which also means chat
   keeps working after the GPU pod is terminated.
"""
import os, pathlib, subprocess, sys, time

APP      = pathlib.Path("/opt/zero-to-llm")
ART      = APP / "artifacts"                 # the backup: model + tokenizer + embeddings
NANOCHAT = APP / "nanochat"                  # code needed to LOAD a checkpoint

_model = None                                # cached (model, tokenizer, engine)


# ---------------------------------------------------------------- backup

def _scp(host, port):
    return ["scp", "-P", str(port), "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-r"]


def save_run(ssh_host, ssh_port, embeddings=True):
    """Pull the trained model off the pod so the demo survives without RunPod."""
    ART.mkdir(parents=True, exist_ok=True)
    scp = _scp(ssh_host, ssh_port)
    got = []

    for remote, label in [("/root/.cache/nanochat/base_checkpoints", "model"),
                          ("/root/.cache/nanochat/tokenizer", "tokenizer")]:
        r = subprocess.run(scp + [f"root@{ssh_host}:{remote}", str(ART)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            got.append(label)
        else:
            print(f"  !! could not save {label}: {r.stderr.strip()[:120]}")

    if embeddings:
        r = subprocess.run(scp + [f"root@{ssh_host}:/workspace/embeddings.parquet", str(ART)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            got.append("embeddings")

    size = sum(f.stat().st_size for f in ART.rglob("*") if f.is_file())
    print(f"Backup saved to {ART} — {', '.join(got)} ({size/1e6:.0f} MB)")
    print("The demo can now run without RunPod.")
    return status()


def status():
    """What do we have banked?"""
    ckpt = list((ART / "base_checkpoints").rglob("*.pt")) if (ART / "base_checkpoints").exists() else []
    tok  = (ART / "tokenizer" / "tokenizer.pkl").exists()
    emb  = (ART / "embeddings.parquet").exists()
    return {"model": bool(ckpt), "tokenizer": tok, "embeddings": emb,
            "path": str(ART)}


def embeddings_path():
    """Where the analysis cells should read from — the saved copy if we have one."""
    local = ART / "embeddings.parquet"
    return str(local) if local.exists() else "embeddings.parquet"


# ---------------------------------------------------------------- local (CPU) generation

def _load():
    """Load the saved checkpoint onto the CPU. Cached — costs a second, once."""
    global _model
    if _model is not None:
        return _model

    st = status()
    if not st["model"] or not st["tokenizer"]:
        raise RuntimeError(
            "No saved model on the droplet yet. Run a training pass first "
            "(the wizard calls save_run() at the end)."
        )

    # nanochat resolves its cache from this env var, so point it at our backup
    os.environ["NANOCHAT_BASE_DIR"] = str(ART)
    os.environ.setdefault("MASTER_ADDR", "localhost")
    os.environ.setdefault("MASTER_PORT", "29500")
    os.environ.setdefault("RANK", "0")
    os.environ.setdefault("WORLD_SIZE", "1")
    os.environ.setdefault("LOCAL_RANK", "0")
    if str(NANOCHAT) not in sys.path:
        sys.path.insert(0, str(NANOCHAT))

    import torch
    from nanochat.checkpoint_manager import load_model
    from nanochat.engine import Engine

    t0 = time.time()
    # nanochat reads device.type internally, so this must be a torch.device —
    # the string "cpu" gets you AttributeError: 'str' object has no attribute 'type'.
    model, tok, meta = load_model("base", torch.device("cpu"), phase="eval")
    engine = Engine(model, tok)
    _model = (model, tok, engine)
    print(f"Model loaded on CPU in {time.time()-t0:.1f}s "
          f"({sum(p.numel() for p in model.parameters())/1e6:.1f}M parameters)")
    return _model


def say(prompt, max_tokens=120, temperature=0.8, top_k=50):
    """Continue `prompt`. This is a BASE model: it continues text, it doesn't answer questions."""
    model, tok, engine = _load()
    toks = [tok.get_bos_token_id()] + tok.encode(prompt)
    out = []
    for tc, _ in engine.generate(toks, num_samples=1, max_tokens=max_tokens,
                                 temperature=temperature, top_k=top_k):
        out.append(tok.decode([tc[0]]))
    return "".join(out)


def warm():
    """Pre-load the model so the first chat message isn't slow."""
    _load()
    return True

# ---------------------------------------------------------------- peer lookup

_emb = None


def _embeddings():
    """Load the banked embeddings once, L2-normalised so a dot product is cosine."""
    global _emb
    if _emb is None:
        import numpy as np, pandas as pd
        f = ART / "embeddings.parquet"
        if not f.exists():
            raise RuntimeError("No embeddings saved on the droplet yet.")
        df = pd.read_parquet(f)
        X = np.stack(df["embedding"].values).astype("float32")
        Xn = X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)
        _emb = (df, Xn)
    return _emb


def peers(ticker, k=8):
    """Nearest companies to `ticker` by cosine similarity of their filing embeddings.

    Returns JSON (the deck parses it). Deduped to one row per company — otherwise the
    top hit is always the same firm in the adjacent year, which is noise. We do keep
    that self-similarity separately, because it's a free sanity check: if a company
    isn't its own nearest neighbour across years, something is broken.
    """
    import json, numpy as np
    t = (ticker or "").strip().upper()
    if not t:
        return json.dumps({"ok": False, "ticker": "", "suggest": []})

    try:
        df, Xn = _embeddings()
    except Exception as e:
        return json.dumps({"ok": False, "ticker": t, "error": str(e), "suggest": []})

    rows = df.index[df["ticker"] == t]
    if len(rows) == 0:
        prefix = t[:2]
        near = sorted({x for x in df["ticker"].unique() if str(x).startswith(prefix)})[:8]
        return json.dumps({"ok": False, "ticker": t, "suggest": [str(x) for x in near]})

    i = int(df.loc[rows].sort_values("year").index[-1])          # its most recent filing
    year = int(df["year"].iloc[i])
    sims = Xn @ Xn[i]

    out, seen, self_sim = [], {t}, None
    for j in np.argsort(-sims):
        j = int(j)
        tj = str(df["ticker"].iloc[j])
        if tj == t:
            if j != i and self_sim is None:
                self_sim = float(sims[j])                        # same firm, other year
            continue
        if tj in seen:
            continue
        seen.add(tj)
        out.append({"t": tj, "y": int(df["year"].iloc[j]), "s": round(float(sims[j]), 4)})
        if len(out) >= k:
            break

    # Every cosine in this space sits high (~0.9+), so a bar drawn from zero is a row of
    # identical full stripes and tells you nothing. Send the mean similarity to the whole
    # corpus as a baseline, so the deck can draw "how much closer than an average company".
    base = float(np.mean(sims))

    return json.dumps({
        "ok": True, "ticker": t, "year": year,
        "self": round(self_sim, 4) if self_sim is not None else None,
        "base": round(base, 4),
        "peers": out, "n": int(len(df)),
    })

# ---------------------------------------------------------------- the GPU meter

POD_NAME = "zero-to-llm"          # only ever touch pods WE created


def _runpod():
    import os, runpod
    key = os.environ.get("RUNPOD_API_KEY")
    if not key:
        # The kernel gets this from systemd's EnvironmentFile, but read it directly
        # too so this works from a plain shell as well — you do NOT want the kill
        # switch to be the thing that turns out to be environment-dependent.
        try:
            for line in (APP / "kernel.env").read_text().splitlines():
                if line.startswith("RUNPOD_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
        except Exception:
            pass
    if not key:
        raise RuntimeError("RUNPOD_API_KEY not found")
    os.environ["RUNPOD_API_KEY"] = key
    runpod.api_key = key
    return runpod


def gpu_status():
    """Is a GPU still burning money? Returns JSON for the deck's meter."""
    import json
    try:
        runpod = _runpod()
        live = [p for p in (runpod.get_pods() or [])
                if p.get("desiredStatus") == "RUNNING" and p.get("name") == POD_NAME]
        return json.dumps({
            "ok": True,
            "n": len(live),
            "pods": [{"id": p["id"], "cost": p.get("costPerHr")} for p in live],
        })
    except Exception as e:
        return json.dumps({"ok": False, "n": 0, "pods": [], "error": str(e)[:120]})


def kill_gpu():
    """Terminate every pod WE started. Never touches a pod with a different name."""
    import json
    try:
        runpod = _runpod()
        killed = []
        for p in (runpod.get_pods() or []):
            if p.get("desiredStatus") == "RUNNING" and p.get("name") == POD_NAME:
                runpod.terminate_pod(p["id"])
                killed.append(p["id"])
        for pid in killed:
            print(f"Terminated pod {pid}")
        if not killed:
            print("No GPU was running.")
        return json.dumps({"ok": True, "killed": killed})
    except Exception as e:
        print(f"Could not terminate: {e}")
        return json.dumps({"ok": False, "killed": [], "error": str(e)[:120]})
