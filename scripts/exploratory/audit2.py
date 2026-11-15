# Copied unchanged from the independent audit (Fable 5.2 reviewer session, 2026-11-15) for reproduction. Exploratory, not pre-registered.
"""Reviewer re-analysis: random-k seed sensitivity and informative-fill ablation. Read-only on project data."""
import json, random, sys, statistics as st
from pathlib import Path
sys.path.insert(0, "src")
from rewardshield.data import load_split
from rewardshield.sqlexec import execute, results_match
from rewardshield.verifiers import build_suite, _informative, _seed

J = lambda p: [json.loads(l) for l in open(p)]
qs = {r["qid"]: r for r in load_split("data/splits/devA.jsonl")}
pool = J("runs/E02/pool_devA.jsonl")
orc = {(o["qid"], o["sample"]): bool(o["oracle"]) for o in J("runs/E03/oracle_devA.jsonl")}
stored = {(v["qid"], v["sample"]): v["verdict"] for v in J("runs/E03/verdicts_devA.jsonl")}
missing = [q for q in qs if not Path("data/cache/suites", q, "cand_23.sqlite").exists()]
print("cache missing for", len(missing), "questions")
assert not missing, "would need to write into the project cache; abort"
suites, sc = {}, {}
rows = []
for rec in pool:
    q = qs[rec["qid"]]
    if rec["qid"] not in suites:
        suites[rec["qid"]] = build_suite(rec["qid"], q["gold"], q["db_path"], "data/cache/suites", schema_cache=sc)
    s, pred = suites[rec["qid"]], rec.get("final_sql")
    m = {}
    if pred:
        for db in [s.original_db] + s.candidates:
            g = s.gold_results[db]
            if not g.ok:
                m[db] = None; continue
            p = execute(db, pred)
            m[db] = bool(p.ok and results_match(g.rows, p.rows, s.ordered))
    rows.append({"qid": rec["qid"], "sample": rec["sample"], "has": bool(pred), "m": m, "oracle": orc[(rec["qid"], rec["sample"])]})

def accept(r, dbs):
    if not r["has"]: return False
    v = [r["m"][d] for d in dbs if r["m"][d] is not None]
    return bool(v) and all(v)
def fa(sel):  # sel(suite) -> db list
    acc = [r for r in rows if accept(r, sel(suites[r["qid"]]))]
    f = sum(1 for r in acc if not r["oracle"])
    fr = sum(1 for r in rows if r["oracle"] and not accept(r, sel(suites[r["qid"]])))
    return len(acc), f, f / len(acc), fr
# 1. reproduce stored
for name, sel in [("single-1", lambda s: s.databases("single", 1)), ("random-4", lambda s: s.databases("random", 4)),
                  ("targeted-4", lambda s: s.databases("targeted", 4)), ("random-16", lambda s: s.databases("random", 16))]:
    mism = sum(1 for r in rows if accept(r, sel(suites[r["qid"]])) != stored[(r["qid"], r["sample"])][name])
    print(f"reproduce {name}: accepts,FA,share,FR = {fa(sel)}  mismatches vs stored = {mism}")
usable = lambda s: [c for c in s.candidates if s.gold_results[c].ok]
inform = lambda s: [c for c in usable(s) if _informative(s.gold_results[c])]
print("\ncandidates per q: usable mean", st.mean(len(usable(s)) for s in suites.values()), "informative mean", round(st.mean(len(inform(s)) for s in suites.values()), 2),
      "| q with <3 informative:", sum(1 for s in suites.values() if len(inform(s)) < 3))
nk = [len(s.mutant_kills) for s in suites.values()]
print("greedy-kill DBs per question (before fill): dist", {k: nk.count(k) for k in sorted(set(nk))}, " mean", round(st.mean(nk), 2),
      "| live mutants mean", round(st.mean(s.n_mutants for s in suites.values()), 2), "killed mean", round(st.mean(s.n_killed for s in suites.values()), 2))
tgt_share = fa(lambda s: s.databases("targeted", 4))[2]
def many(label, pick, k, n=300):
    shares, fas, frs = [], [], []
    for sd in range(n):
        def sel(s):
            rng = random.Random(_seed(s.qid, label, str(sd)))
            c = pick(s)
            return [s.original_db] + rng.sample(c, min(k - 1, len(c)))
        a, f, sh, fr = fa(sel); shares.append(sh); fas.append(f); frs.append(fr)
    shares.sort()
    print(f"{label:28s} k={k:2d} over {n} seeds: FA count mean {st.mean(fas):5.1f} [min {min(fas)}, max {max(fas)}]  share mean {100*st.mean(shares):.2f}% (2.5-97.5 pct {100*shares[int(.025*n)]:.2f}-{100*shares[int(.975*n)-1]:.2f})  FR mean {st.mean(frs):.1f}  P(share<=targeted-4 {100*tgt_share:.2f}%)={sum(1 for x in shares if x <= tgt_share)/n:.3f}")
print()
many("random(usable)", usable, 4)
many("random(informative-only)", lambda s: inform(s) or usable(s), 4)
many("random(usable)", usable, 8)
many("random(informative-only)", lambda s: inform(s) or usable(s), 8)
many("random(usable)", usable, 16)
many("random(informative-only)", lambda s: inform(s) or usable(s), 16)
print()
print("targeted-4 (as shipped: kills + informative fill):", fa(lambda s: s.databases("targeted", 4)))
print("targeted kills-only (<=3 greedy DBs, no fill):   ", fa(lambda s: [s.original_db] + s.targeted_order[: min(3, len(s.mutant_kills))]))
for k in (2, 3, 4, 6, 8):
    print(f"targeted-{k}:", fa(lambda s: s.databases("targeted", k)))
print("all 24 candidates + original:", fa(lambda s: [s.original_db] + usable(s)))
# FA of the shipped targeted-4 that all-25 would catch; and oracle-accepted that all-25 rejects
a25 = lambda r: accept(r, [suites[r["qid"]].original_db] + usable(suites[r["qid"]]))
print("oracle-TRUE samples rejected by all-25 (oracle possibly too lenient):", sum(1 for r in rows if r["oracle"] and r["has"] and not a25(r)),
      "over questions", len({r["qid"] for r in rows if r["oracle"] and r["has"] and not a25(r)}))
print("oracle-FALSE samples accepted by all-25:", sum(1 for r in rows if not r["oracle"] and a25(r)))
