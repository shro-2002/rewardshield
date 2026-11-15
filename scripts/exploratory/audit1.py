# Copied unchanged from the independent audit (Fable 5.2 reviewer session, 2026-11-15) for reproduction. Exploratory, not pre-registered.
import json, random, sys, math
from collections import Counter, defaultdict
R = sys.argv[1]
J = lambda p: [json.loads(l) for l in open(f"{R}/{p}")]
ver = J("runs/E03/verdicts_devA.jsonl"); orc = {(o["qid"], o["sample"]): o["oracle"] for o in J("runs/E03/oracle_devA.jsonl")}
rows = [{**v, "oracle": bool(orc[(v["qid"], v["sample"])])} for v in ver]
keys = ["single-1", "agenttune", "random-4", "targeted-4", "random-16"]
print("n", len(rows), "oracle true", sum(r["oracle"] for r in rows), "has_sql", sum(r["has_sql"] for r in rows))
print("\n== False accepts: samples / distinct questions / distinct dbs / per-db counts")
fa = {}
for k in keys:
    f = [r for r in rows if r["verdict"][k] and not r["oracle"]]
    fa[k] = f
    print(f"{k:11s} acc={sum(r['verdict'][k] for r in rows)} FA={len(f)} q={len({r['qid'] for r in f})} db={len({r['db_id'] for r in f})}", dict(Counter(r["db_id"] for r in f)))
print("\n== False rejects (oracle true, verifier rejects)")
for k in keys:
    f = [r for r in rows if not r["verdict"][k] and r["oracle"]]
    print(f"{k:11s} FR={len(f)} q={len({r['qid'] for r in f})}", dict(Counter(r["db_id"] for r in f)))
# discordance targeted vs random-4 on oracle-wrong samples
def disc(a, b):
    w = [r for r in rows if not r["oracle"] and r["has_sql"]]
    only_a = [r for r in w if r["verdict"][a] and not r["verdict"][b]]
    only_b = [r for r in w if r["verdict"][b] and not r["verdict"][a]]
    return only_a, only_b
for a, b in [("single-1", "targeted-4"), ("random-4", "targeted-4"), ("random-16", "targeted-4")]:
    oa, ob = disc(a, b)
    print(f"\nwrong samples accepted only by {a}: {len(oa)} (q={len({r['qid'] for r in oa})}, db={dict(Counter(r['db_id'] for r in oa))}); only by {b}: {len(ob)} (q={len({r['qid'] for r in ob})})")
    # question-level sign test: questions where a has more FA than b vs reverse
    perq = defaultdict(lambda: [0, 0])
    for r in rows:
        if not r["oracle"]:
            perq[r["qid"]][0] += r["verdict"][a]; perq[r["qid"]][1] += r["verdict"][b]
    more_a = sum(1 for x in perq.values() if x[0] > x[1]); more_b = sum(1 for x in perq.values() if x[1] > x[0])
    n = more_a + more_b
    p = sum(math.comb(n, i) for i in range(0, min(more_a, more_b) + 1)) / 2 ** n * 2 if n else 1
    print(f"  question-level: {a} worse on {more_a} q, {b} worse on {more_b} q; two-sided sign test p={min(p,1):.4f}")

def metrics(rs, k):
    acc = [r for r in rs if r["verdict"][k]]
    return (sum(1 for r in acc if not r["oracle"]) / len(acc)) if acc else None
def boot(field, a, b, n=10000, seed=20261114):
    g = defaultdict(list)
    for r in rows: g[r[field]].append(r)
    ks = list(g); rng = random.Random(seed); d = []
    for _ in range(n):
        s = [r for k in rng.choices(ks, k=len(ks)) for r in g[k]]
        x, y = metrics(s, a), metrics(s, b)
        if x is not None and y is not None: d.append(y - x)
    d.sort(); return d[int(.025 * len(d))], d[int(.975 * len(d)) - 1], sum(1 for v in d if v >= 0) / len(d)
print("\n== bootstrap CI of FA-share diff (b - a): question-level vs schema-level (10 dbs)")
for a, b in [("single-1", "targeted-4"), ("random-4", "targeted-4"), ("random-16", "targeted-4"), ("single-1", "random-4")]:
    pt = metrics(rows, b) - metrics(rows, a)
    print(f"{b} - {a}: pt={pt*100:+.2f}  Q-CI={[round(x*100,2) for x in boot('qid', a, b)[:2]]}  DB-CI={[round(x*100,2) for x in boot('db_id', a, b)[:2]]}  P(diff>=0|db boot)={boot('db_id', a, b)[2]:.3f}")
print("\n== leave-one-db-out FA share diffs (targeted-4 minus random-4 ; minus single-1)")
for db in sorted({r["db_id"] for r in rows}):
    rs = [r for r in rows if r["db_id"] != db]
    print(f"  drop {db:24s} t4-r4={100*(metrics(rs,'targeted-4')-metrics(rs,'random-4')):+.2f}  t4-s1={100*(metrics(rs,'targeted-4')-metrics(rs,'single-1')):+.2f}  FA r4={sum(1 for r in rs if r['verdict']['random-4'] and not r['oracle'])} t4={sum(1 for r in rs if r['verdict']['targeted-4'] and not r['oracle'])}")
print("\n== per-db FA counts by verifier and accepted counts")
for db in sorted({r["db_id"] for r in rows}):
    rs = [r for r in rows if r["db_id"] == db]
    print(f"  {db:24s} n={len(rs):4d} " + " ".join(f"{k}:{sum(1 for r in rs if r['verdict'][k] and not r['oracle'])}/{sum(r['verdict'][k] for r in rs)}" for k in keys))
# question-level collapse: FA at question-level
print("\n== unique (qid, final-sql-equivalence unknown) : FA samples per question distribution")
for k in ["single-1", "random-4", "targeted-4"]:
    print(k, sorted(Counter(r["qid"] for r in fa[k]).values(), reverse=True))
