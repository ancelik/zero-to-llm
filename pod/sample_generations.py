"""
Pod-side. Loads the just-trained base model and prints completions for a
handful of SEC-flavored prompts. Run automatically by train_workshop.py at
the end of training, or by hand:

    python /workspace/zero-to-llm/pod/sample_generations.py

Note: the base model only does autocomplete (no SFT was run). Prompts are
phrased as the *start* of an SEC filing snippet; the model continues it.
"""

import sys
import pathlib

# Import shared inference helpers
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _inference import load_base_engine, complete

PROMPTS = [
    "ITEM 1A. RISK FACTORS\n\nThe following risks could materially affect our",
    "Our business is focused on",
    "We may be unable to",
    "Management's Discussion and Analysis of Financial Condition and Results of Operations\n\nOverview:",
    "We are a",
]


def main():
    print("Loading the just-trained base model ...")
    engine, tokenizer, meta, device = load_base_engine()
    print(f"  Model loaded on {device}. Vocab={tokenizer.get_vocab_size()}, "
          f"Params={meta.get('model_config', {}).get('n_layer', '?')} layers.")

    for i, prompt in enumerate(PROMPTS):
        print()
        print("-" * 70)
        print(f"Prompt {i + 1}:  {prompt!r}")
        print("Continuation:")
        print(prompt, end="")
        complete(engine, tokenizer, prompt, max_tokens=120, temperature=0.8, top_k=50)


if __name__ == "__main__":
    main()
