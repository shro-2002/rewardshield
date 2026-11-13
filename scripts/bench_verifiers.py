"""Verifier cost and adversarial coverage on gold queries (no model samples).

For each question: build the suite, then score every gold mutant (deliberately adversarial, kept
separate from model samples) with single, random-k and targeted-k. A mutant that the original
database cannot tell from gold but random/targeted can is a would-be false accept caught.
Note: some mutants are equivalent to gold, so "accepted" here is not automatically an error.
Run: uv run python scripts/bench_verifiers.py --split data/splits/devA.jsonl --out runs/bench_devA
"""

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from rewardshield.mutants import generate_mutants  # noqa: E402
from rewardshield.verifiers import build_suite, verify  # noqa: E402

MODES = [("single", 1), ("random", 4), ("targeted", 4), ("random", 16)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rows = [json.loads(line) for line in open(args.split)]
    rows = rows[: args.limit] if args.limit else rows
    schema_cache: dict = {}
    records = []
    for r in rows:
        suite = build_suite(r["qid"], r["gold"], r["db_path"], str(out / "cache"), schema_cache=schema_cache)
        rec = {"qid": r["qid"], "hardness": r["hardness"], "build_s": round(suite.build_seconds, 3),
               "n_live_mutants": suite.n_mutants, "n_killed": suite.n_killed, "accepted": {}, "verify_ms": {}}
        for mutant in generate_mutants(r["gold"]):
            for mode, k in MODES:
                key = f"{mode}-{k}"
                start = time.perf_counter()
                v = verify(suite, mutant, mode, k)
                rec["verify_ms"].setdefault(key, []).append((time.perf_counter() - start) * 1000)
                rec["accepted"][key] = rec["accepted"].get(key, 0) + int(v.accept)
        records.append(rec)
    with open(out / "per_question.jsonl", "w") as fh:
        for rec in records:
            fh.write(json.dumps({**rec, "verify_ms": {k: round(statistics.median(v), 3) for k, v in rec["verify_ms"].items()}}) + "\n")
    summary = {
        "n_questions": len(records),
        "build_s_median": statistics.median(r["build_s"] for r in records),
        "build_s_total": round(sum(r["build_s"] for r in records), 1),
        "live_mutants_total": sum(r["n_live_mutants"] for r in records),
        "killed_by_targeted_pool": sum(r["n_killed"] for r in records),
        "mutants_accepted": {f"{m}-{k}": sum(r["accepted"].get(f"{m}-{k}", 0) for r in records) for m, k in MODES},
        "verify_ms_median": {f"{m}-{k}": round(statistics.median(x for r in records for x in r["verify_ms"].get(f"{m}-{k}", [0])), 3)
                             for m, k in MODES},
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
