"""Build schema-disjoint Spider splits: train (train databases), dev-A and dev-B (dev databases).

Keeps easy and medium questions (official Spider hardness), applies the pre-registered exclusions
and writes data/splits/{train,devA,devB}.jsonl plus a summary with every exclusion count.
Run: uv run python scripts/build_splits.py --spider data/raw/spider_zip/spider
"""

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "third_party" / "test-suite-sql-eval"))
sys.path.insert(0, str(ROOT / "src"))

from evaluation import Evaluator  # noqa: E402  (official Spider hardness)

from rewardshield.sqlexec import execute  # noqa: E402

KEEP_HARDNESS = {"easy", "medium"}
DEV_SPLIT_SEED = 20261114


def _limit_without_order(sql: str) -> bool:
    low = " ".join(sql.lower().split())
    return " limit " in f" {low} " and " order by " not in low


def load(spider: Path, files: list[str], split: str) -> list[dict]:
    rows = []
    for name in files:
        for i, ex in enumerate(json.loads((spider / name).read_text())):
            rows.append({"qid": f"{split}-{Path(name).stem}-{i:05d}", "db_id": ex["db_id"], "question": ex["question"],
                         "gold": ex["query"], "parsed": ex["sql"]})
    return rows


def classify(rows: list[dict], spider: Path) -> tuple[list[dict], Counter]:
    evaluator, kept, dropped = Evaluator(), [], Counter()
    for r in rows:
        r["hardness"] = evaluator.eval_hardness(r.pop("parsed"))
        r["db_path"] = str(spider / "database" / r["db_id"] / f"{r['db_id']}.sqlite")
        if r["hardness"] not in KEEP_HARDNESS:
            dropped["hardness_" + r["hardness"]] += 1
        elif _limit_without_order(r["gold"]):
            dropped["limit_without_order"] += 1
        elif not execute(r["db_path"], r["gold"]).ok:
            dropped["gold_fails"] += 1
        else:
            kept.append(r)
    return kept, dropped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spider", default="data/raw/spider_zip/spider")
    ap.add_argument("--out", default="data/splits")
    args = ap.parse_args()
    spider, out = Path(args.spider), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    train, train_drop = classify(load(spider, ["train_spider.json", "train_others.json"], "train"), spider)
    dev, dev_drop = classify(load(spider, ["dev.json"], "dev"), spider)
    dev_dbs = sorted({r["db_id"] for r in dev})
    random.Random(DEV_SPLIT_SEED).shuffle(dev_dbs)
    dev_a_dbs = set(dev_dbs[: len(dev_dbs) // 2])
    splits = {"train": train,
              "devA": [r for r in dev if r["db_id"] in dev_a_dbs],
              "devB": [r for r in dev if r["db_id"] not in dev_a_dbs]}
    assert not ({r["db_id"] for r in train} & set(dev_dbs)), "train and dev databases must be disjoint"
    for name, rows in splits.items():
        with open(out / f"{name}.jsonl", "w") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")
    summary = {
        "seed": DEV_SPLIT_SEED,
        "counts": {k: len(v) for k, v in splits.items()},
        "databases": {k: len({r["db_id"] for r in v}) for k, v in splits.items()},
        "hardness": {k: dict(Counter(r["hardness"] for r in v)) for k, v in splits.items()},
        "dev_a_dbs": sorted(dev_a_dbs),
        "dev_b_dbs": sorted(set(dev_dbs) - dev_a_dbs),
        "dropped_train": dict(train_drop),
        "dropped_dev": dict(dev_drop),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
