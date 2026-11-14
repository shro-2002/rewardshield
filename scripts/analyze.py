"""Pre-registered analysis (HYPOTHESES.md). Pure functions + two CLIs.

verifiers: uv run python scripts/analyze.py verifiers --verdicts runs/E03/verdicts.jsonl --oracle runs/E03/oracle.jsonl
arms:      uv run python scripts/analyze.py arms --a runs/E04/devB_oracle.jsonl --b runs/E05/devB_oracle.jsonl
Oracle files: JSONL with qid, sample, oracle (true/false/null). Null rows are excluded and counted.
"""

import argparse
import json
import random
from collections import defaultdict

N_BOOT = 10_000
SEED = 20261114


def verifier_metrics(rows: list[dict], key: str) -> dict:
    acc = [r for r in rows if r["verdict"][key]]
    fa = [r for r in acc if not r["oracle"]]
    pos = [r for r in rows if r["oracle"]]
    fr = [r for r in pos if not r["verdict"][key]]
    return {"n": len(rows), "accepted": len(acc), "coverage": len(acc) / len(rows) if rows else None,
            "false_accept_share": len(fa) / len(acc) if acc else None,
            "false_accept_mass": len(fa) / len(rows) if rows else None,
            "false_reject_rate": len(fr) / len(pos) if pos else None}


def _by(rows: list[dict], field: str) -> dict:
    groups = defaultdict(list)
    for r in rows:
        groups[r[field]].append(r)
    return groups


def bootstrap(groups: dict, stat, n_boot: int = N_BOOT, seed: int = SEED) -> tuple[float, float, float]:
    """Point estimate and 95% percentile interval, resampling whole groups (questions or schemas)."""
    keys = list(groups)
    point = stat([r for k in keys for r in groups[k]])
    rng = random.Random(seed)
    draws = []
    for _ in range(n_boot):
        sample = [r for k in rng.choices(keys, k=len(keys)) for r in groups[k]]
        value = stat(sample)
        if value is not None:
            draws.append(value)
    draws.sort()
    return point, draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1]


def fa_share_diff(a: str, b: str):
    """Statistic: false-accept share of verifier b minus verifier a (negative = b better)."""
    def stat(rows):
        sa, sb = verifier_metrics(rows, a)["false_accept_share"], verifier_metrics(rows, b)["false_accept_share"]
        return None if sa is None or sb is None else sb - sa
    return stat


def verdict_label(lo: float, hi: float, predicted_sign: int) -> str:
    if (predicted_sign < 0 and hi < 0) or (predicted_sign > 0 and lo > 0):
        return "supported"
    if (predicted_sign < 0 and lo > 0) or (predicted_sign > 0 and hi < 0):
        return "refuted"
    return "inconclusive"


def load_joined(verdicts: str, oracle: str) -> tuple[list[dict], int]:
    orc = {(o["qid"], o["sample"]): o["oracle"] for o in map(json.loads, open(oracle))}
    rows, excluded = [], 0
    for v in map(json.loads, open(verdicts)):
        label = orc.get((v["qid"], v["sample"]))
        if label is None:
            excluded += 1
            continue
        rows.append({**v, "oracle": bool(label)})
    return rows, excluded


def cli_verifiers(args) -> dict:
    rows, excluded = load_joined(args.verdicts, args.oracle)
    keys = list(rows[0]["verdict"])
    out = {"excluded_no_oracle": excluded, "metrics": {k: verifier_metrics(rows, k) for k in keys}}
    q = _by(rows, "qid")
    tests = {"H1 targeted-4 vs single-1": ("single-1", "targeted-4"), "H2 targeted-4 vs random-4": ("random-4", "targeted-4"),
             "S1 targeted-4 vs random-16": ("random-16", "targeted-4")}
    out["tests"] = {}
    for name, (a, b) in tests.items():
        point, lo, hi = bootstrap(q, fa_share_diff(a, b))
        label = verdict_label(lo, hi, -1) if name[0] == "H" else ("within 1pt" if lo > -0.01 and hi < 0.01 else "not shown")
        out["tests"][name] = {"diff": point, "ci95": [lo, hi], "result": label}
    return out


def cli_arms(args) -> dict:
    def acc(path):
        return {r["qid"]: float(bool(r["oracle"])) for r in map(json.loads, open(path)) if r.get("sample", 0) == 0}
    a, b = acc(args.a), acc(args.b)
    db = {r["qid"]: r.get("db_id") for r in map(json.loads, open(args.a))}
    common = sorted(set(a) & set(b))
    rows = [{"qid": q, "db_id": db.get(q), "d": b[q] - a[q]} for q in common]

    def mean_d(rs):
        return sum(r["d"] for r in rs) / len(rs) if rs else None
    out = {"n_questions": len(common), "acc_a": sum(a[q] for q in common) / len(common),
           "acc_b": sum(b[q] for q in common) / len(common)}
    for level, field in (("question", "qid"), ("schema", "db_id")):
        point, lo, hi = bootstrap(_by(rows, field), mean_d)
        out[f"diff_{level}"] = {"diff": point, "ci95": [lo, hi]}
    lo, hi = out["diff_question"]["ci95"]
    out["H3"] = verdict_label(lo, hi, +1)
    out["practical"] = "no practical difference" if abs(out["diff_question"]["diff"]) < 0.02 else "difference >= 2 points"
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("verifiers")
    v.add_argument("--verdicts", required=True)
    v.add_argument("--oracle", required=True)
    a = sub.add_parser("arms")
    a.add_argument("--a", required=True, help="single-filtered arm (baseline)")
    a.add_argument("--b", required=True, help="targeted-filtered arm")
    args = ap.parse_args()
    result = cli_verifiers(args) if args.cmd == "verifiers" else cli_arms(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
