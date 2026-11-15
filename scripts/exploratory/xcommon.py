"""Shared loader for the exploratory union-oracle / flight_2 / blind-label analyses (not pre-registered).

load(split) returns (rows, suites, questions). One row per sample:
  qid, sample, arm, db_id, question, gold, pred, has, oracle,
  m: {db_path: True/False/None} on the original DB + 24 generated candidates (None = gold fails there),
  verdict: {single-1, random-4, targeted-4, random-16, agenttune}.
dev-A verdicts are the stored E03 verdicts (checked against a recomputation); dev-B verdicts are computed
here with the shipped seeds. dev-A suites are read from the project cache (never written); dev-B suites go
to a private scratch dir. No result cache (rebuilt on every run, about 90 s).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from rewardshield.data import load_split  # noqa: E402
from rewardshield.sqlexec import execute, results_match  # noqa: E402
from rewardshield.verifiers import build_suite  # noqa: E402

SCRATCH = Path("/private/tmp/claude-501/-Users-shroddhaghosh-Desktop-Hackathons-Lexsi---AI-Safety-and-Alignment-Hackathon/"
               "eef47f4c-9d5e-40ea-b1ca-9b29d6434a6d/scratchpad")
DEVB_CACHE = SCRATCH / "devB_suites_union"
DEVA_CACHE = ROOT / "data/cache/suites"
ARMS = ["E00", "E01", "E04", "E05"]
KEYS = ["single-1", "agenttune", "random-4", "targeted-4", "random-16"]
SEL = {"single-1": ("single", 1), "random-4": ("random", 4), "targeted-4": ("targeted", 4), "random-16": ("random", 16)}


def qi(name: str) -> str:
    """Quote an SQL identifier SQLite-style. Names come only from sqlite_master/PRAGMA of local read-only databases."""
    return '"' + name.replace('"', '""') + '"'


def read_jsonl(p):
    return [json.loads(line) for line in open(ROOT / p)]


def accept(row: dict, dbs: list[str]) -> bool:
    v = [row["m"][d] for d in dbs if row["m"].get(d) is not None]
    return row["has"] and bool(v) and all(v)


def all_dbs(suite) -> list[str]:
    return [suite.original_db] + suite.candidates


def _matches(suite, pred: str | None) -> dict:
    m = {}
    if not pred:
        return m
    for db in all_dbs(suite):
        g = suite.gold_results[db]
        if not g.ok:
            m[db] = None
            continue
        p = execute(db, pred)
        m[db] = bool(p.ok and results_match(g.rows, p.rows, suite.ordered))
    return m


def _records(split: str):
    if split == "devA":
        orc = {(o["qid"], o["sample"]): o["oracle"] for o in read_jsonl("runs/E03/oracle_devA.jsonl")}
        ver = {(v["qid"], v["sample"]): v["verdict"] for v in read_jsonl("runs/E03/verdicts_devA.jsonl")}
        for r in read_jsonl("runs/E02/pool_devA.jsonl"):
            yield r, "pool", orc[(r["qid"], r["sample"])], ver[(r["qid"], r["sample"])]
        return
    for arm in ARMS:
        orc = {o["qid"]: o["oracle"] for o in read_jsonl(f"runs/E04/out/{arm}_devB_oracle.jsonl")}
        for r in read_jsonl(f"runs/E04/out/{arm}_devB.jsonl"):
            yield r, arm, orc[r["qid"]], None


def _agenttune(db_path: str, gold: str, pred: str) -> bool:
    from score_samples import agenttune_verdict  # shipped baseline implementation
    return agenttune_verdict(db_path, gold, pred)


def load(split: str):
    qs = {r["qid"]: r for r in load_split(str(ROOT / f"data/splits/{split}.jsonl"))}
    for q in qs.values():
        q["db_path"] = str(ROOT / q["db_path"])
    cache = DEVA_CACHE if split == "devA" else DEVB_CACHE
    if split == "devA":
        missing = [q for q in qs if not (cache / q / "cand_23.sqlite").exists()]
        assert not missing, "dev-A cache incomplete; refusing to write into the project cache"
    suites, sc, rows = {}, {}, []
    for rec, arm, orc, stored in _records(split):
        q = qs[rec["qid"]]
        if rec["qid"] not in suites:
            suites[rec["qid"]] = build_suite(rec["qid"], q["gold"], q["db_path"], str(cache), schema_cache=sc)
        s, pred = suites[rec["qid"]], rec.get("final_sql")
        row = {"qid": rec["qid"], "sample": rec.get("sample", 0), "arm": arm, "db_id": q["db_id"],
               "question": q["question"], "gold": q["gold"], "pred": pred, "has": bool(pred),
               "oracle": bool(orc), "oracle_raw": orc, "m": _matches(s, pred)}
        computed = {k: accept(row, s.databases(*SEL[k])) for k in SEL}
        computed["agenttune"] = bool(pred) and _agenttune(q["db_path"], q["gold"], pred)
        row["verdict_recomputed"] = computed
        row["verdict"] = {k: bool(stored[k]) for k in KEYS} if stored else computed
        rows.append(row)
    return rows, suites, qs


if __name__ == "__main__":
    for sp in ("devA", "devB"):
        rows, suites, _ = load(sp)
        mism = {k: sum(r["verdict"][k] != r["verdict_recomputed"][k] for r in rows) for k in KEYS}
        print(sp, "rows", len(rows), "questions", len(suites), "stored-vs-recomputed verdict mismatches", mism,
              "oracle None", sum(r["oracle_raw"] is None for r in rows))
