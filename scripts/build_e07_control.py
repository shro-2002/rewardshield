"""E07 gold control: gold trajectories for a question set matched to the E04/E05 arms.

Questions (rule fixed in DECISIONS.md 2026-11-15 10:05, before E07 runs): every question both arms
share, plus an equal number drawn (seed 0) from each arm's unique questions, so the set has the arms'
size (911) and leans towards neither arm. Each question gets the same gold trajectory format as the
E01 warm start (one tool call with the gold SQL, its real result, a templated reply).

uv run python scripts/build_e07_control.py --arms runs/E04/sft_single-1.jsonl runs/E04/sft_targeted-4.jsonl \
    --pool-split data/splits/train_pool_1200.jsonl --out runs/E07
"""

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rewardshield.agent import gold_trajectory  # noqa: E402
from rewardshield.data import load_split  # noqa: E402


def matched_questions(arm_a: list[str], arm_b: list[str], seed: int) -> list[str]:
    """Shared questions plus equal draws from each arm's unique questions, up to the arm size."""
    a, b = set(arm_a), set(arm_b)
    shared, only_a, only_b = sorted(a & b), sorted(a - b), sorted(b - a)
    per_arm = (len(arm_a) - len(shared)) // 2
    rng = random.Random(seed)
    picked = shared + rng.sample(only_a, per_arm) + rng.sample(only_b, len(arm_a) - len(shared) - per_arm)
    return sorted(picked)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs=2, required=True)
    ap.add_argument("--pool-split", default="data/splits/train_pool_1200.jsonl")
    ap.add_argument("--out", default="runs/E07")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    arms = [[json.loads(line) for line in open(p)] for p in args.arms]
    qids = matched_questions([r["qid"] for r in arms[0]], [r["qid"] for r in arms[1]], args.seed)
    by_q = {r["qid"]: r for r in load_split(args.pool_split)}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    gold_chars = []
    with open(out / "sft_gold_matched.jsonl", "w") as fh:
        for q in qids:
            r = by_q[q]
            msgs = gold_trajectory(r["question"], r["gold"], r["db_path"])
            gold_chars.append(sum(len(m["content"]) for m in msgs[2:]))
            fh.write(json.dumps({"qid": q, "messages": msgs}) + "\n")
    arm_chars = {Path(p).stem: statistics.median(sum(len(m["content"]) for m in r["messages"][2:]) for r in rows)
                 for p, rows in zip(args.arms, arms)}
    summary = {"seed": args.seed, "n": len(qids), "shared_with_both_arms": len(set(qids) & {r["qid"] for r in arms[0]} & {r["qid"] for r in arms[1]}),
               "median_completion_chars": {"gold": statistics.median(gold_chars), **arm_chars}}
    (out / "e07_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
