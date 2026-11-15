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

usable = lambda s: [c for c in s.candidates if s.gold_results[c].ok]
inform = lambda s: [c for c in usable(s) if _informative(s.gold_results[c])]
N = 300
def dist(label, selmaker):
    fas, shares, frs = [], [], []
    for sd in range(N):
        a, f, sh, fr = fa(selmaker(sd)); fas.append(f); shares.append(sh); frs.append(fr)
    shares.sort(); fas_s = sorted(fas)
    print(f"{label:52s} FA mean {st.mean(fas):5.2f} sd {st.pstdev(fas):.2f} [min {min(fas)} / 2.5% {fas_s[int(.025*N)]} / med {fas_s[N//2]} / 97.5% {fas_s[int(.975*N)-1]} / max {max(fas)}]  share mean {100*st.mean(shares):.2f}%  FR mean {st.mean(frs):.1f}")
    return fas
def kills(s): return s.targeted_order[: len(s.mutant_kills)]
def tgt_fill(pool_fn, k):
    def mk(sd):
        def sel(s):
            kd = kills(s)[: k - 1]
            rest = [c for c in pool_fn(s) if c not in kd]
            other = [c for c in usable(s) if c not in kd and c not in rest]
            rng = random.Random(_seed(s.qid, "refill", str(sd))); rng.shuffle(rest); rng.shuffle(other)
            return [s.original_db] + (kd + rest + other)[: k - 1]
        return sel
    return mk
def rnd(pool_fn, k):
    def mk(sd):
        def sel(s):
            rng = random.Random(_seed(s.qid, "rnd", str(sd))); c = pool_fn(s) or usable(s)
            extra = [x for x in usable(s) if x not in c]
            rng.shuffle(c := list(c)); rng.shuffle(extra)
            return [s.original_db] + (c + extra)[: k - 1]
        return sel
    return mk
print("shipped targeted-4 (one fill seed):", fa(lambda s: s.databases("targeted", 4))[:2], "| shipped random-4 (one seed):", fa(lambda s: s.databases("random", 4))[:2])
A = dist("targeted-4 = mutant-kill DBs + informative fill (reseeded)", tgt_fill(inform, 4))
B = dist("mutant-kill DBs + plain random fill", tgt_fill(usable, 4))
C = dist("random-4, informative-first (no mutants)", rnd(inform, 4))
D = dist("random-4, plain (as pre-registered)", rnd(usable, 4))
# paired by seed index is meaningless; compare distributions
import itertools
def p_less(x, y): return sum(1 for a, b in itertools.product(x, y) if a < b) / (len(x) * len(y)), sum(1 for a, b in itertools.product(x, y) if a == b) / (len(x) * len(y))
print("P(targeted FA < random-plain FA), P(tie):", p_less(A, D))
print("P(targeted FA < random-informative FA), P(tie):", p_less(A, C))
print("P(kill+random-fill < random-plain), P(tie):", p_less(B, D))
# where does the mutant part act? restrict to the 102 questions with >=1 kill DB
kq = {q for q, s in suites.items() if s.mutant_kills}
sub = [r for r in rows if r["qid"] in kq]
print(f"\nquestions with >=1 mutant-kill DB: {len(kq)}; samples {len(sub)}; oracle-wrong & single-accepted there: {sum(1 for r in sub if not r['oracle'] and accept(r,[suites[r['qid']].original_db]))}; elsewhere: {sum(1 for r in rows if r['qid'] not in kq and not r['oracle'] and accept(r,[suites[r['qid']].original_db]))}")
caught = [r for r in rows if not r["oracle"] and accept(r, [suites[r["qid"]].original_db]) and not accept(r, [suites[r["qid"]].original_db] + kills(suites[r["qid"]]))]
print("single-accepted wrong samples that a mutant-kill DB catches:", len(caught), "over questions", len({r['qid'] for r in caught}))
# k sweep means
for k in (2, 3, 4, 6, 8):
    a = [fa(tgt_fill(inform, k)(sd))[1] for sd in range(60)]; d = [fa(rnd(usable, k)(sd))[1] for sd in range(60)]
    print(f"k={k}: targeted(reseeded fill) mean FA {st.mean(a):.1f} | random plain mean FA {st.mean(d):.1f}")
