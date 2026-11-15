# Copied unchanged from the independent audit (Fable 5.2 reviewer session, 2026-11-15) for reproduction. Exploratory, not pre-registered.
"""Reviewer check: out-of-sample replication of H1/H2 on dev-B greedy outputs (E00/E01/E04/E05). Exploratory.
Suite cache goes to a scratch dir (argv[1]); nothing is written into the project."""
import json, random, sys, statistics as st, itertools
sys.path.insert(0, "src")
from rewardshield.data import load_split
from rewardshield.sqlexec import execute, results_match
from rewardshield.verifiers import build_suite, _informative, _seed
CACHE = sys.argv[1]
J = lambda p: [json.loads(l) for l in open(p)]
qs = {r["qid"]: r for r in load_split("data/splits/devB.jsonl")}
suites, sc, rows = {}, {}, []
for arm in ["E00", "E01", "E04", "E05"]:
    orc = {r["qid"]: bool(r["oracle"]) for r in J(f"runs/E04/out/{arm}_devB_oracle.jsonl")}
    for rec in J(f"runs/E04/out/{arm}_devB.jsonl"):
        q = qs[rec["qid"]]
        if rec["qid"] not in suites:
            suites[rec["qid"]] = build_suite(rec["qid"], q["gold"], q["db_path"], CACHE, schema_cache=sc)
        s, pred, m = suites[rec["qid"]], rec.get("final_sql"), {}
        if pred:
            for db in [s.original_db] + s.candidates:
                g = s.gold_results[db]
                if g.ok:
                    p = execute(db, pred); m[db] = bool(p.ok and results_match(g.rows, p.rows, s.ordered))
        rows.append({"qid": rec["qid"], "arm": arm, "db_id": q["db_id"], "has": bool(pred), "m": m, "oracle": orc[rec["qid"]]})
# dedupe identical (qid, pred) across arms would understate n; keep all, cluster by question
def accept(r, dbs):
    v = [r["m"][d] for d in dbs if d in r["m"]]
    return r["has"] and bool(v) and all(v)
def fa(sel, rs=rows):
    acc = [r for r in rs if accept(r, sel(suites[r["qid"]]))]
    return len(acc), sum(1 for r in acc if not r["oracle"])
usable = lambda s: [c for c in s.candidates if s.gold_results[c].ok]
inform = lambda s: [c for c in usable(s) if _informative(s.gold_results[c])]
kills = lambda s: s.targeted_order[: len(s.mutant_kills)]
print("dev-B samples", len(rows), "with SQL", sum(r["has"] for r in rows), "oracle-correct", sum(r["oracle"] for r in rows), "questions", len(suites))
nk = [len(s.mutant_kills) for s in suites.values()]
print("questions with >=1 mutant-kill DB:", sum(1 for x in nk if x), "of", len(nk), "| mean kill DBs", round(st.mean(nk), 2), "| mean live mutants", round(st.mean(s.n_mutants for s in suites.values()), 2))
for name, sel in [("single-1", lambda s: s.databases("single", 1)), ("random-4 (shipped seed)", lambda s: s.databases("random", 4)),
                  ("targeted-4 (shipped seed)", lambda s: s.databases("targeted", 4)), ("random-16 (shipped seed)", lambda s: s.databases("random", 16)),
                  ("kill-DBs only", lambda s: [s.original_db] + kills(s)[:3]), ("all 25", lambda s: [s.original_db] + usable(s))]:
    a, f = fa(sel); q = {r["qid"] for r in rows if accept(r, sel(suites[r["qid"]])) and not r["oracle"]}
    print(f"{name:26s} accepts {a:5d}  FA {f:3d} ({100*f/a:.2f}%)  FA questions {len(q)}")
N = 200
def tgt(sd):
    def sel(s):
        kd = kills(s)[:3]; rest = [c for c in inform(s) if c not in kd]; other = [c for c in usable(s) if c not in kd and c not in rest]
        rng = random.Random(_seed(s.qid, "refill", str(sd))); rng.shuffle(rest); rng.shuffle(other)
        return [s.original_db] + (kd + rest + other)[:3]
    return sel
def rnd(sd):
    def sel(s):
        rng = random.Random(_seed(s.qid, "rnd", str(sd))); return [s.original_db] + rng.sample(usable(s), min(3, len(usable(s))))
    return sel
T = [fa(tgt(i))[1] for i in range(N)]; R = [fa(rnd(i))[1] for i in range(N)]
d = lambda x: f"mean {st.mean(x):.1f} sd {st.pstdev(x):.1f} [min {min(x)}, 2.5% {sorted(x)[int(.025*N)]}, 97.5% {sorted(x)[int(.975*N)-1]}, max {max(x)}]"
print("reseeded targeted-4 FA:", d(T)); print("reseeded random-4   FA:", d(R))
print("P(targeted<random), P(tie):", sum(1 for a, b in itertools.product(T, R) if a < b) / N**2, sum(1 for a, b in itertools.product(T, R) if a == b) / N**2)
print("per-arm single-1 FA share:", {a: "%d/%d" % fa(lambda s: s.databases("single", 1), [r for r in rows if r["arm"] == a])[::-1] for a in ["E00", "E01", "E04", "E05"]})
print("per-arm all-25 rejects of oracle-correct:", {a: sum(1 for r in rows if r["arm"] == a and r["oracle"] and not accept(r, [suites[r["qid"]].original_db] + usable(suites[r["qid"]]))) for a in ["E00", "E01", "E04", "E05"]})
