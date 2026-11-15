"""Score recorded trajectories with RewardShield inside AgentTune's own rollout loop (CPU, no model).

Each recorded episode is replayed through agenttune create_rollout_fn (ReplayEngine supplies the
recorded assistant turns; AgentTune parses the tool calls, runs the real run_sql tool and calls the
reward through _wrap_reward_fn). Prints replay fidelity (replayed final SQL == recorded final SQL)
and how each verifier's reward agrees with the test-suite oracle labels.
uv run python scripts/demo_agenttune_reward.py --records runs/E04/out/E05_devB.jsonl \
    --oracle runs/E04/out/E05_devB_oracle.jsonl --split data/splits/devB.jsonl --limit 40
"""

import argparse
import json
import sys
import tempfile
import time
import warnings
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agenttune.agentic.rollout_engines.rollout_factory import create_rollout_fn  # noqa: E402

from rewardshield.agent import final_sql, make_run_sql  # noqa: E402
from rewardshield.agenttune_reward import ReplayEngine, RewardShieldReward  # noqa: E402
from rewardshield.data import load_split  # noqa: E402


def replay(records: list[dict], questions: dict, reward: RewardShieldReward) -> list[dict]:
    """One AgentTune rollout_fn per database (its tool is bound to that database)."""
    by_db: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        by_db[questions[rec["qid"]]["db_path"]].append(rec)
    rows = []
    for db, recs in by_db.items():
        rollout_fn = create_rollout_fn(rollout_engine=ReplayEngine([r["messages"] for r in recs]),
                                       tools=[make_run_sql(db)], max_steps=4, reward_fn=reward)
        prompts = [{"prompt": questions[r["qid"]]["question"], "gold_sql": questions[r["qid"]]["gold"],
                    "db_path": db, "qid": r["qid"]} for r in recs]
        out = rollout_fn(prompts)
        for rec, conv, score in zip(recs, out["conversations"], out["rewards"]):
            rows.append({"qid": rec["qid"], "sample": rec["sample"], "reward": score,
                         "same_sql": final_sql(conv) == rec.get("final_sql")})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default="runs/E04/out/E05_devB.jsonl")
    ap.add_argument("--oracle", default="runs/E04/out/E05_devB_oracle.jsonl")
    ap.add_argument("--split", default="data/splits/devB.jsonl")
    ap.add_argument("--limit", type=int, default=40, help="first N records (0 = all)")
    ap.add_argument("--cache", default=None, help="suite cache dir (default: a temp dir)")
    args = ap.parse_args()
    warnings.simplefilter("ignore")  # AgentTune warns once per rollout_fn about tool templates
    questions = {q["qid"]: q for q in load_split(args.split)}
    records = [json.loads(line) for line in open(args.records)]
    records = records[: args.limit] if args.limit else records
    oracle = {(o["qid"], o["sample"]): o["oracle"] for o in map(json.loads, open(args.oracle))}
    cache = args.cache or tempfile.mkdtemp(prefix="rewardshield-demo-")
    print(f"{len(records)} recorded episodes from {args.records}; suites in {cache}")
    for mode, k in [("single", 1), ("targeted", 4)]:
        start = time.perf_counter()
        rows = replay(records, questions, RewardShieldReward(mode, k, cache_dir=cache))
        secs = time.perf_counter() - start
        acc = [r for r in rows if r["reward"] > 0]
        false_acc = sum(1 for r in acc if not oracle[(r["qid"], r["sample"])])
        false_rej = sum(1 for r in rows if r["reward"] <= 0 and oracle[(r["qid"], r["sample"])])
        print(f"{mode}-{k}: replay fidelity {sum(r['same_sql'] for r in rows)}/{len(rows)}, "
              f"accepts {len(acc)}, oracle-wrong accepts {false_acc}, oracle-correct rejects {false_rej}, "
              f"{secs:.1f} s (incl. suite build)")


if __name__ == "__main__":
    main()
