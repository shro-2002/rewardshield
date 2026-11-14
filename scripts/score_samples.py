"""Score rollout samples with every verifier (CPU). Oracle verdicts are joined later.

Verifiers: single, random-4, targeted-4, random-16 (rewardshield) and agenttune (AgentTune 1.1.5
result_match_reward on the original database: multiset rows, order ignored, no column permutation).
uv run python scripts/score_samples.py --samples runs/E02/pool.jsonl --split data/splits/train_pool.jsonl \
    --out runs/E02/verdicts.jsonl
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from agenttune.agentic.rewards.builtin_rewards.sql import result_match_reward  # noqa: E402

from rewardshield.data import load_split  # noqa: E402
from rewardshield.sqlexec import execute  # noqa: E402
from rewardshield.verifiers import build_suite, verify  # noqa: E402

VERIFIERS = [("single", 1), ("random", 4), ("targeted", 4), ("random", 16)]


def agenttune_verdict(db_path: str, gold: str, pred: str) -> bool:
    gold_res, pred_res = execute(db_path, gold), execute(db_path, pred)
    if not (gold_res.ok and pred_res.ok):
        return False
    call = {"function": {"name": "run_sql", "arguments": json.dumps({"sql_command": pred})}}
    conv = [{"role": "assistant", "content": "", "tool_calls": [call]},
            {"role": "tool", "content": [list(r) for r in pred_res.rows]}]
    return result_match_reward([""], gold_rows=[[list(r) for r in gold_res.rows]], conversations=[conv])[0] > 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cache", default="data/cache/suites")
    args = ap.parse_args()
    questions = {r["qid"]: r for r in load_split(args.split)}
    suites, schema_cache = {}, {}
    out = open(args.out, "w")
    for rec in map(json.loads, open(args.samples)):
        q = questions[rec["qid"]]
        if rec["qid"] not in suites:
            suites[rec["qid"]] = build_suite(rec["qid"], q["gold"], q["db_path"], args.cache, schema_cache=schema_cache)
        suite, pred = suites[rec["qid"]], rec.get("final_sql")
        row = {"qid": rec["qid"], "sample": rec["sample"], "db_id": q["db_id"], "hardness": q["hardness"],
               "has_sql": bool(pred), "n_tool_calls": rec.get("n_tool_calls"), "build_s": round(suite.build_seconds, 4),
               "verdict": {}, "n_exec": {}, "ms": {}}
        for mode, k in VERIFIERS:
            key = f"{mode}-{k}"
            v = verify(suite, pred, mode, k) if pred else None
            row["verdict"][key] = bool(v and v.accept)
            row["n_exec"][key] = v.n_exec if v else 0
            row["ms"][key] = round(v.ms, 3) if v else 0.0
        start = time.perf_counter()
        row["verdict"]["agenttune"] = bool(pred) and agenttune_verdict(q["db_path"], q["gold"], pred)
        row["ms"]["agenttune"] = round((time.perf_counter() - start) * 1000, 3)
        out.write(json.dumps(row) + "\n")
    out.close()
    print(f"scored {sum(1 for _ in open(args.out))} samples over {len(suites)} questions")


if __name__ == "__main__":
    main()
