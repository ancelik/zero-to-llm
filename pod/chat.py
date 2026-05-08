"""
Pod-side. Interactive REPL with the just-trained base model.

Important: this is a *base* model (no instruction tuning). It's an
autocomplete machine, not a chatbot. So treat your prompt as the *start*
of a passage that the model should continue. For best results, write
prompts that look like SEC filing fragments, e.g.:

    > Our principal risks include
    > ITEM 1A. RISK FACTORS\n\n
    > The Company was incorporated in

Commands:
    :quit, :exit       leave the REPL
    :temp 0.5          set temperature (default 0.8)
    :topk 20           set top_k (default 50)
    :tokens 300        set max_tokens (default 200)
    :seed 123          set random seed
    :reload            re-load the model from the latest checkpoint
    :help              show these commands

Usage (run from inside the pod, after training has finished):
    python /workspace/zero-to-llm/pod/chat.py
"""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _inference import load_base_engine, complete


HELP = """
Commands:
  :quit / :exit       leave
  :temp <float>       sampling temperature
  :topk <int>         top-k sampling
  :tokens <int>       max generation length
  :seed <int>         random seed
  :reload             reload the latest checkpoint
  :help               this help
"""


def main():
    print("Loading the just-trained base model ...")
    engine, tokenizer, meta, device = load_base_engine()
    print(f"  Model loaded on {device}. Vocab={tokenizer.get_vocab_size()}.")
    print()
    print("=" * 70)
    print("  Interactive autocomplete with your tiny SEC LLM.")
    print("  This is a BASE model — write your prompt as the START of a passage.")
    print("  Type :help for commands, :quit to exit.")
    print("=" * 70)

    settings = {"temperature": 0.8, "top_k": 50, "max_tokens": 200, "seed": 42}

    while True:
        try:
            line = input("\n> ")
        except (EOFError, KeyboardInterrupt):
            print("\nbye.")
            return

        s = line.strip()
        if not s:
            continue
        if s.startswith(":"):
            parts = s.split()
            cmd = parts[0][1:]
            if cmd in ("quit", "exit"):
                return
            if cmd == "help":
                print(HELP); continue
            if cmd == "reload":
                engine, tokenizer, meta, device = load_base_engine()
                print("  reloaded."); continue
            if cmd in ("temp", "topk", "tokens", "seed") and len(parts) == 2:
                key = {"temp": "temperature", "topk": "top_k", "tokens": "max_tokens", "seed": "seed"}[cmd]
                try:
                    settings[key] = type(settings[key])(parts[1])
                    print(f"  {key} = {settings[key]}")
                except ValueError:
                    print(f"  bad value for {key}: {parts[1]}")
                continue
            print(f"  unknown command: {cmd}. try :help"); continue

        # Otherwise: treat the line as a prompt and complete it.
        # We render the prompt back so the user sees the full context.
        print(s, end="")
        complete(
            engine, tokenizer, s,
            max_tokens=settings["max_tokens"],
            temperature=settings["temperature"],
            top_k=settings["top_k"],
        )


if __name__ == "__main__":
    main()
