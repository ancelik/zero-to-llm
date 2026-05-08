# zero-to-llm

Train a tiny LLM on SEC filings on a RunPod GPU, then explore the embeddings locally. The whole pipeline is driven from `train.ipynb` running on your laptop — RunPod is only used as a remote GPU box.

## Quick start

Requires Python 3.10+ and `ssh` / `scp` / `ssh-keygen` (pre-installed on Linux, macOS, and WSL).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter lab train.ipynb
```

Then put the SEC parquets in `data/filings-2025-2026/` (they aren't in the repo — get them from the workshop storage pod), open the notebook, paste your RunPod API key in cell 1, and run cells top-to-bottom.

## What's in `requirements.txt`

Only the bootstrap layer needed to open the notebook and run its first cells:

- `jupyterlab` — to open `train.ipynb`
- `runpod` — imported in cell 1 to control the GPU pod (pulls `requests` transitively)

Everything else is either Python stdlib (`subprocess`, `pathlib`, `getpass`, `time`) or installed by the notebook itself when you reach section 14 (`pandas`, `pyarrow`, `scikit-learn`, `matplotlib`, `numpy`).

## Setup notes (read if `pip install` or `jupyter lab` fails)

- **Always use a venv.** On Ubuntu 22.04+ the system Python is PEP 668 "externally managed" and will refuse `pip install` without a venv.
- **`python3 -m venv .venv` fails with "ensurepip is not available"** → install the venv module: `sudo apt install python3-venv` on Debian/Ubuntu.
- **`jupyter lab` opens but the kernel can't import `runpod`** → you launched Jupyter from outside the venv. Re-activate (`source .venv/bin/activate`) and relaunch.
- **No `python3` on the machine** → install Python 3.10+ first (`sudo apt install python3` on Debian/Ubuntu, `brew install python` on macOS).
