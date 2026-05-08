"""
Shared loading + generation helpers used by sample_generations.py and chat.py.

Imports nanochat directly, so this module must be imported under the
nanochat venv (the launcher activates it for you).
"""

import torch

from nanochat.checkpoint_manager import load_model
from nanochat.common import autodetect_device_type, compute_init
from nanochat.engine import Engine


def load_base_engine(device_type: str = ""):
    """Load the just-pretrained base model and return (engine, tokenizer, meta, device)."""
    device_type = autodetect_device_type() if not device_type else device_type
    _ddp, _rank, _local_rank, _ws, device = compute_init(device_type)
    model, tokenizer, meta = load_model(
        "base", device, phase="eval",
        model_tag=None, step=None,  # auto-pick the largest model + last step
    )
    engine = Engine(model, tokenizer)
    return engine, tokenizer, meta, device


def complete(engine, tokenizer, prompt: str, max_tokens: int = 200,
             temperature: float = 0.8, top_k: int = 50, stream=True):
    """
    Continue `prompt` for up to max_tokens. Returns the generated string.
    If stream=True, also prints tokens as they arrive.
    """
    bos = tokenizer.get_bos_token_id()
    prompt_tokens = [bos] + tokenizer.encode(prompt)
    out_pieces = []
    for token_column, _masks in engine.generate(
        prompt_tokens,
        num_samples=1,
        max_tokens=max_tokens,
        temperature=temperature,
        top_k=top_k,
    ):
        token = token_column[0]
        text = tokenizer.decode([token])
        out_pieces.append(text)
        if stream:
            print(text, end="", flush=True)
    if stream:
        print()
    return "".join(out_pieces)
