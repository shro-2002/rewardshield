"""Roll out the SQL agent on a split. Resumable: existing (qid, sample) records are skipped.

uv run python scripts/run_rollouts.py --model ~/models/tiny-aya-global --split data/splits/devB.jsonl \
    --n 1 --temperature 0 --out runs/E00/devB.jsonl [--adapter runs/E01/adapter] [--limit 50]
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rewardshield.data import load_split  # noqa: E402
from rewardshield.rollout import run_rollouts  # noqa: E402


def load_model(model_path: str, adapter: str | None, dtype: str):
    device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    tok = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForCausalLM.from_pretrained(model_path, dtype=getattr(torch, dtype)).to(device)
    if adapter:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, adapter).merge_and_unload()
    model.eval()
    return model, tok


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--adapter")
    ap.add_argument("--split", required=True)
    ap.add_argument("--spider-root")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-new-tokens", type=int, default=192)
    ap.add_argument("--max-steps", type=int, default=4)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dtype", default="float16" if torch.cuda.is_available() else "bfloat16")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    items = load_split(args.split, args.spider_root)[args.offset:]
    items = items[: args.limit] if args.limit else items
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        done = {(r["qid"], r["sample"]) for r in map(json.loads, out.open())}
    todo = [it for it in items if any((it["qid"], s) not in done for s in range(args.n))]
    print(f"{len(items)} items, {len(todo)} to do", flush=True)
    model, tok = load_model(os.path.expanduser(args.model), args.adapter, args.dtype)
    start = time.perf_counter()
    with out.open("a") as fh:
        def write(rec: dict) -> None:
            if (rec["qid"], rec["sample"]) not in done:
                fh.write(json.dumps({**rec, "seed": args.seed, "temperature": args.temperature,
                                     "adapter": args.adapter}) + "\n")
                fh.flush()
        run_rollouts(model, tok, todo, n=args.n, temperature=args.temperature, max_steps=args.max_steps,
                     max_new_tokens=args.max_new_tokens, batch_size=args.batch_size, on_done=write)
    secs = time.perf_counter() - start
    print(json.dumps({"rollouts": len(todo) * args.n, "seconds": round(secs, 1),
                      "rollouts_per_min": round(60 * len(todo) * args.n / max(secs, 1e-9), 1)}), flush=True)


if __name__ == "__main__":
    main()
