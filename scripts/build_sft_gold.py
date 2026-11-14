"""Gold-trajectory SFT data for the warm start (E01), from train-database questions only.

Questions are split by database into a warm-start half and a pool half so the pool (E02) uses
questions the warm start never saw. Sizes are recorded in the output summary.
uv run python scripts/build_sft_gold.py --n-warm 1500 --out runs/E01
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rewardshield.agent import gold_trajectory  # noqa: E402
from rewardshield.data import load_split  # noqa: E402

SEED = 20261114


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default="data/splits/train.jsonl")
    ap.add_argument("--n-warm", type=int, default=1500)
    ap.add_argument("--out", default="runs/E01")
    args = ap.parse_args()
    rows = load_split(args.train)
    dbs = sorted({r["db_id"] for r in rows})
    random.Random(SEED).shuffle(dbs)
    warm_dbs = set(dbs[: len(dbs) // 2])
    warm = [r for r in rows if r["db_id"] in warm_dbs]
    pool = [r for r in rows if r["db_id"] not in warm_dbs]
    random.Random(SEED).shuffle(warm)
    warm = warm[: args.n_warm]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "sft_gold.jsonl", "w") as fh:
        for r in warm:
            fh.write(json.dumps({"qid": r["qid"], "messages": gold_trajectory(r["question"], r["gold"], r["db_path"])}) + "\n")
    with open("data/splits/train_pool.jsonl", "w") as fh:
        for r in pool:
            fh.write(json.dumps(r) + "\n")
    summary = {"seed": SEED, "warm_dbs": len(warm_dbs), "pool_dbs": len(dbs) - len(warm_dbs),
               "warm_examples": len(warm), "pool_questions": len(pool)}
    (out / "sft_gold_summary.json").write_text(json.dumps(summary, indent=2))
    print(summary)


if __name__ == "__main__":
    main()
