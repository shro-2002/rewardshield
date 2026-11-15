# Copied unchanged from the independent audit (Fable 5.2 reviewer session, 2026-11-15) for reproduction. Exploratory, not pre-registered.
"""Reviewer check: seed-marginalised, question-bootstrapped H2 (targeted-4 vs random-4) on dev-A pool and dev-B greedy outputs.
Exploratory. argv[1] = scratch cache dir for dev-B suites. Nothing written into the project."""
import json, random, sys, statistics as st
from collections import defaultdict, Counter
sys.path.insert(0, "src")
from rewardshield.data import load_split
from rewardshield.sqlexec import execute, results_match
from rewardshield.verifiers import build_suite, _informative, _seed
J = lambda p: [json.loads(l) for l in open(p)]
NSEED, NBOOT = 200, 5000

def load(split):
    if split == "devA":
        qs = {r["qid"]: r for r in load_split("data/splits/devA.jsonl")}
        orc = {(o["qid"], o["sample"]): bool(o["oracle"]) for o in J("runs/E03/oracle_devA.jsonl")}
        recs = [(r["qid"], r.get("final_sql"), orc[(r["qid"], r["sample"])]) for r in J("runs/E02/pool_devA.jsonl")]
        return qs, recs, "data/cache/suites"
    qs = {r["qid"]: r for r in load_split("data/splits/devB.jsonl")}
    recs, seen = [], set()
    for arm in ["E00", "E01", "E04", "E05"]:
        orc = {r["qid"]: bool(r["oracle"]) for r in J(f"runs/E04/out/{arm}_devB_oracle.jsonl")}
        for r in J(f"runs/E04/out/{arm}_devB.jsonl"):
            key = (r["qid"], " ".join((r.get("final_sql") or "").lower().split()))
            if key in seen: continue  # conservative: one row per distinct (question, SQL)
            seen.add(key); recs.append((r["qid"], r.get("final_sql"), orc[r["qid"]]))
    return qs, recs, sys.argv[1]

def run(split):
    qs, recs, cache = load(split)
    suites, sc, rows = {}, {}, []
    for qid, pred, o in recs:
        if qid not in suites:
            suites[qid] = build_suite(qid, qs[qid]["gold"], qs[qid]["db_path"], cache, schema_cache=sc)
        s, m = suites[qid], {}
        if pred:
            for db in [s.original_db] + s.candidates:
                g = s.gold_results[db]
                if g.ok:
                    p = execute(db, pred); m[db] = bool(p.ok and results_match(g.rows, p.rows, s.ordered))
        rows.append({"qid": qid, "db_id": qs[qid]["db_id"], "has": bool(pred), "m": m, "oracle": o})
    usable = lambda s: [c for c in s.candidates if s.gold_results[c].ok]
    def acc(r, dbs):
        v = [r["m"][d] for d in dbs if d in r["m"]]; return r["has"] and bool(v) and all(v)
    def tsel(s, sd):
        kd = s.targeted_order[: len(s.mutant_kills)][:3]
        rest = [c for c in usable(s) if _informative(s.gold_results[c]) and c not in kd]; other = [c for c in usable(s) if c not in kd and c not in rest]
        rng = random.Random(_seed(s.qid, "refill", str(sd))); rng.shuffle(rest); rng.shuffle(other)
        return [s.original_db] + (kd + rest + other)[:3]
    def rsel(s, sd):
        rng = random.Random(_seed(s.qid, "rnd", str(sd))); return [s.original_db] + rng.sample(usable(s), min(3, len(usable(s))))
    # per question: expected (over seeds) accepts and false accepts under each verifier
    Q = defaultdict(lambda: {"ta": 0.0, "tf": 0.0, "ra": 0.0, "rf": 0.0, "sa": 0, "sf": 0, "db": None})
    for sd in range(NSEED):
        selT = {q: tsel(s, sd) for q, s in suites.items()}; selR = {q: rsel(s, sd) for q, s in suites.items()}
        for r in rows:
            q = Q[r["qid"]]; q["db"] = r["db_id"]
            if acc(r, selT[r["qid"]]): q["ta"] += 1 / NSEED; q["tf"] += (not r["oracle"]) / NSEED
            if acc(r, selR[r["qid"]]): q["ra"] += 1 / NSEED; q["rf"] += (not r["oracle"]) / NSEED
    for r in rows:
        if acc(r, [suites[r["qid"]].original_db]): Q[r["qid"]]["sa"] += 1; Q[r["qid"]]["sf"] += not r["oracle"]
    def stat(keys):
        ta = sum(Q[k]["ta"] for k in keys); tf = sum(Q[k]["tf"] for k in keys); ra = sum(Q[k]["ra"] for k in keys); rf = sum(Q[k]["rf"] for k in keys)
        sa = sum(Q[k]["sa"] for k in keys); sf = sum(Q[k]["sf"] for k in keys)
        return tf / ta - rf / ra, tf - rf, tf / ta, rf / ra, sf / sa, tf / ta - sf / sa
    keys = list(Q); pt = stat(keys)
    print(f"\n=== {split}: rows {len(rows)} (questions {len(keys)}), expected over {NSEED} seeds")
    print(f"single-1 FA share {100*pt[4]:.2f}% | random-4 {100*pt[3]:.2f}% | targeted-4 {100*pt[2]:.2f}% | H2 diff {100*pt[0]:+.2f} pts ({pt[1]:+.1f} FA samples) | H1 diff {100*pt[5]:+.2f} pts")
    for level, grp in (("question", {k: [k] for k in keys}), ("schema", {d: [k for k in keys if Q[k]["db"] == d] for d in {Q[k]["db"] for k in keys}})):
        rng, d2, d1 = random.Random(20261115), [], []
        g = list(grp)
        for _ in range(NBOOT):
            ks = [k for c in rng.choices(g, k=len(g)) for k in grp[c]]
            v = stat(ks); d2.append(v[0]); d1.append(v[5])
        d2.sort(); d1.sort()
        ci = lambda d: f"[{100*d[int(.025*NBOOT)]:+.2f}, {100*d[int(.975*NBOOT)-1]:+.2f}]"
        print(f"  {level:8s} bootstrap: H2 CI {ci(d2)}  P(diff>=0)={sum(1 for x in d2 if x >= 0)/NBOOT:.3f} | H1 CI {ci(d1)}")
    per = defaultdict(lambda: [0.0, 0.0, 0])
    for k in keys:
        per[Q[k]["db"]][0] += Q[k]["tf"]; per[Q[k]["db"]][1] += Q[k]["rf"]; per[Q[k]["db"]][2] += Q[k]["sf"]
    print("  per-schema expected FA (targeted / random / single):", {d: f"{v[0]:.1f}/{v[1]:.1f}/{v[2]}" for d, v in sorted(per.items()) if v[2]})
    worse = sum(1 for k in keys if Q[k]["tf"] > Q[k]["rf"] + 1e-9); better = sum(1 for k in keys if Q[k]["tf"] < Q[k]["rf"] - 1e-9)
    print(f"  questions where targeted has lower expected FA: {better}; higher: {worse}")
for sp in ("devA", "devB"): run(sp)
