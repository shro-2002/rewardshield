"""Greedy parity: rewardshield batched rollouts vs AgentTune's rollout_fn on the same questions.

Reports how often both produce the same final SQL. Batching (left padding) can change greedy
tokens slightly in fp16, so exact agreement is reported, not assumed.
python scripts/check_rollout_parity.py --model $MODEL --split data/splits/devA.jsonl --spider-root $SPIDER --n 12
"""

import argparse
import json
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rewardshield.agent import final_sql, make_run_sql, system_prompt  # noqa: E402
from rewardshield.data import load_split  # noqa: E402
from rewardshield.rollout import run_rollouts  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--spider-root")
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--out", default="parity.json")
    args = ap.parse_args()
    from agenttune.agentic.rollout_engines.rollout_factory import create_rollout_engine, create_rollout_fn

    device = "cuda" if torch.cuda.is_available() else "mps"
    tok = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.float16 if device == "cuda" else torch.bfloat16).to(device)
    items = load_split(args.split, args.spider_root)[: args.n]
    ours = {r["qid"]: r["final_sql"] for r in run_rollouts(model, tok, items, temperature=0.0, batch_size=8)}
    engine = create_rollout_engine(backend="transformers", model=model, tokenizer=tok)
    same, rows = 0, []
    for it in items:
        fn = create_rollout_fn(rollout_engine=engine, tools=[make_run_sql(it["db_path"])], max_steps=4,
                               system_prompt=system_prompt(it["db_path"]))
        conv = fn([it["question"]], do_sample=False, max_new_tokens=192)["conversations"][0]
        theirs = final_sql(conv)
        same += int((theirs or "").strip().rstrip(";") == (ours[it["qid"]] or "").strip().rstrip(";"))
        rows.append({"qid": it["qid"], "agenttune": theirs, "rewardshield": ours[it["qid"]]})
    result = {"n": len(items), "same_final_sql": same, "rows": rows}
    Path(args.out).write_text(json.dumps(result, indent=2))
    print(json.dumps({"n": len(items), "same_final_sql": same}))


if __name__ == "__main__":
    main()
