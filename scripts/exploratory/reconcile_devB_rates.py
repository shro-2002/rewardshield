"""Reconcile the dev-B single-1 false-accept shares reported by the audit (18.1%) and by our flight_2 study (12.1%).

Same verifier, different populations. Prints accepts, false accepts and share for each population, with and
without the 45 questions whose gold is degenerate on the original database. Exploratory; reads stored files only.
uv run python scripts/exploratory/reconcile_devB_rates.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from rewardshield.data import load_split  # noqa: E402
from rewardshield.sqlexec import execute, results_match  # noqa: E402

MODELS = ["E00", "E01", "E04", "E05"]


def load_rows() -> list[dict]:
    qs = {r["qid"]: r for r in load_split(str(ROOT / "data/splits/devB.jsonl"))}
    rows = []
    for m in MODELS:
        orc = {r["qid"]: bool(r["oracle"]) for r in map(json.loads, open(ROOT / f"runs/E04/out/{m}_devB_oracle.jsonl"))}
        for r in map(json.loads, open(ROOT / f"runs/E04/out/{m}_devB.jsonl")):
            q, pred = qs[r["qid"]], r.get("final_sql")
            ok = False
            if pred:
                g, p = execute(q["db_path"], q["gold"]), execute(q["db_path"], pred)
                ok = bool(g.ok and p.ok and results_match(g.rows, p.rows, "order by" in q["gold"].lower()))
            rows.append({"model": m, "qid": r["qid"], "db_id": q["db_id"], "pred": pred, "single": ok, "oracle": orc[r["qid"]]})
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    """The audit's population: one row per (question, whitespace-normalised lower-case SQL), first model wins."""
    seen, out = set(), []
    for r in rows:
        key = (r["qid"], " ".join((r["pred"] or "").lower().split()))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def share(rows: list[dict]) -> str:
    acc = [r for r in rows if r["single"]]
    fa = [r for r in acc if not r["oracle"]]
    return f"rows {len(rows):5d}  accepts {len(acc):4d}  FA {len(fa):3d}  share {100 * len(fa) / len(acc):5.2f}%  flight_2 FA {sum(r['db_id'] == 'flight_2' for r in fa)}"


def main() -> None:
    rows = load_rows()
    degen = {q["qid"] for q in map(json.loads, open(ROOT / "runs/exploratory/flight2/questions.jsonl"))
             if q["split"] == "devB" and q["degenerate_original"]}
    pops = {"all rows (4 models x 379)": rows, "distinct (question, SQL), audit": dedupe(rows)}
    for name, rs in pops.items():
        print(f"{name:34s} {share(rs)}")
        print(f"{'  without 45 degenerate questions':34s} {share([r for r in rs if r['qid'] not in degen])}")
    for m in MODELS:
        print(f"{'  model ' + m:34s} {share([r for r in rows if r['model'] == m])}")
    correct_acc = [r for r in rows if r["single"] and r["oracle"]]
    wrong_acc = [r for r in rows if r["single"] and not r["oracle"]]
    d = dedupe(rows)
    print(f"dedupe keeps {sum(r['single'] and r['oracle'] for r in d)}/{len(correct_acc)} correct accepts "
          f"and {sum(r['single'] and not r['oracle'] for r in d)}/{len(wrong_acc)} wrong accepts")


if __name__ == "__main__":
    main()
