"""Build matched-count SFT sets, one per verifier arm (rule fixed in DECISIONS.md 2026-11-14 13:50).

Per arm: keep questions with at least one accepted sample, pick one accepted sample per question
at random, then subsample every arm to N = the smallest accepted-question count over the arms.

uv run python scripts/build_arm_sets.py --pool runs/E02/pool_train.jsonl --verdicts runs/E02/verdicts_train.jsonl \
    --arms single-1 targeted-4 --out-dir runs/E04
"""

import argparse
import json
import random
from pathlib import Path


def build_arms(verdicts: list[dict], arms: list[str], seed: int) -> tuple[dict, dict]:
    """Return ({arm: sorted [(qid, sample)]}, stats). Pure, so the rule is testable without a pool."""
    rng = random.Random(seed)
    picked = {}
    for arm in arms:
        by_q: dict[str, list[int]] = {}
        for v in verdicts:
            if v["verdict"][arm]:
                by_q.setdefault(v["qid"], []).append(v["sample"])
        picked[arm] = {q: rng.choice(sorted(s)) for q, s in sorted(by_q.items())}
    n = min(len(p) for p in picked.values())
    arms_out, stats = {}, {"n": n, "accepted_questions": {a: len(p) for a, p in picked.items()}}
    for arm, p in picked.items():
        keep = rng.sample(sorted(p), n)
        arms_out[arm] = sorted((q, p[q]) for q in keep)
    return arms_out, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", required=True)
    ap.add_argument("--verdicts", required=True)
    ap.add_argument("--arms", nargs="+", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    verdicts = [json.loads(line) for line in open(args.verdicts)]
    pool = {(r["qid"], r["sample"]): r["messages"] for r in map(json.loads, open(args.pool))}
    arms, stats = build_arms(verdicts, args.arms, args.seed)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for arm, keys in arms.items():
        with open(out / f"sft_{arm}.jsonl", "w") as fh:
            for qid, sample in keys:
                fh.write(json.dumps({"qid": qid, "sample": sample, "messages": pool[(qid, sample)]}) + "\n")
    (out / "arms_summary.json").write_text(json.dumps({**stats, "seed": args.seed, "arms": args.arms}, indent=2))
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
