"""Regenerate a distilled Spider test suite with the original authors' generator.

Uses ruiqi-zhong/TestSuiteEval (cloned in oracle/TestSuiteEval) unmodified:
  - fuzz.fuzz.generate_random_db_with_queries_wrapper  (random database sampler, Sec 4.1)
  - fuzz.neighbor.generate_neighbor_queries_path        (neighbor queries N_g, Sec 3.1)
  - sql_util.eq.result_eq                               (denotation comparison)
and the greedy distillation loop from TestSuiteEval/demo.ipynb (Sec 4.2 / App. A.1).

Per db_id: sample a pool of random DBs whose constants come from all Spider-dev gold
queries of that db (as the authors' DBFuzzer does), then for every unique devA/devB
gold query greedily keep pool DBs that distinguish a still-undistinguished neighbor.
Suite = original DB + union of kept DBs, written as data/oracle/test_suite/<db>/<db>[k].sqlite.

Disk discipline (hard limits from the coordinator): db_ids are processed one at a time,
at most 40 candidates per db (15 for wta_1, whose original is 100 MB), every candidate is VACUUMed
right after generation (the authors' writer copies the full original and DROPs tables
without VACUUM, so a wta_1 candidate is ~100 MB of free pages otherwise), candidates
over 20 MB are discarded, unselected candidates are deleted before the next db_id, and
the run aborts if data/oracle exceeds 4 GB.

Run:  PYTHONHASHSEED=0 oracle/.venv/bin/python oracle/build_suite.py
"""
import argparse
import contextlib
import io
import json
import multiprocessing as mp
import os
import random
import shutil
import sqlite3
import sys
import time
import zlib

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TSE = os.path.join(ROOT, "oracle", "TestSuiteEval")
sys.path.insert(0, TSE)
from fuzz.fuzz import generate_random_db_with_queries_wrapper  # noqa: E402
from fuzz.neighbor import generate_neighbor_queries_path  # noqa: E402
from sql_util.eq import result_eq  # noqa: E402
from sql_util.run import replace_cur_year  # noqa: E402

SPIDER = os.path.join(ROOT, "data", "raw", "spider_zip", "spider")
SPLITS = [os.path.join(ROOT, "data", "splits", f) for f in ("devA.jsonl", "devB.jsonl")]
OUT = os.path.join(ROOT, "data", "oracle", "test_suite")
POOL = os.path.join(ROOT, "data", "oracle", "_pool")
ORIG = os.path.join(ROOT, "data", "oracle", "_orig")  # private copies: the generator writes temp files beside its input
GOLD_TIMEOUT_S = 2.0      # a pool DB is dropped if any gold query exceeds this
NEIGHBOR_TIMEOUT_S = 0.5  # per neighbor execution
MAX_STRIKES = 3           # neighbor dropped after this many timeouts
QUERY_BUDGET_S = 600      # wall budget for distilling one gold query
DEFAULT_CANDIDATES = 40
LARGE_DB_CANDIDATES = {"wta_1": 15}  # only wta_1 is large (100 MB); car_1 65 KB, world_1 320 KB
MAX_CANDIDATE_BYTES = 20 * 2**20
MAX_ORACLE_BYTES = 4 * 2**30
LARGE_ORIG_BYTES = 20 * 2**20  # originals this big get fewer parallel workers (transient copies)


def seed_for(*parts) -> int:
    return zlib.crc32("|".join(map(str, parts)).encode())


def run_sql(path: str, query: str, timeout: float):
    """Mirror of sql_util.run.exec_db_path_ plus an in-process timeout (progress handler)."""
    conn = sqlite3.connect(path)
    conn.text_factory = lambda b: b.decode(errors="ignore")
    deadline = time.monotonic() + timeout
    conn.set_progress_handler(lambda: time.monotonic() > deadline, 10000)
    try:
        return "result", conn.execute(replace_cur_year(query)).fetchall()
    except sqlite3.OperationalError as e:
        return ("timeout", None) if "interrupted" in str(e) else ("exception", e)
    except Exception as e:  # noqa: BLE001 - any failure means "no denotation"
        return "exception", e
    finally:
        conn.close()


def spider_path(db: str) -> str:
    return os.path.join(SPIDER, "database", db, db + ".sqlite")


def orig_path(db: str) -> str:
    return os.path.join(ORIG, db, db + ".sqlite")


def make_pool_db(args):
    db, i, seed, queries = args
    target = os.path.join(POOL, db, f"{db}_pool{i}.sqlite")
    random.seed(seed_for(seed, db, i))
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            generate_random_db_with_queries_wrapper((orig_path(db), target, queries, {}))
        except Exception as e:  # noqa: BLE001 - record and skip broken samples
            if os.path.exists(target):
                os.unlink(target)
            return db, i, f"error: {e!r}"
    conn = sqlite3.connect(target)
    conn.execute("VACUUM")
    conn.close()
    if os.path.getsize(target) > MAX_CANDIDATE_BYTES:
        os.unlink(target)
        return db, i, "too_big"
    return db, i, "ok"


def check_pool_db(args):
    """Return (db, path, gold denotations) or (db, path, None) if any gold fails/slow."""
    db, path, golds = args
    dens = {}
    for g in golds:
        flag, den = run_sql(path, g, GOLD_TIMEOUT_S)
        if flag != "result":
            return db, path, None
        dens[g] = den
    return db, path, dens


def distill(args):
    db, gold, seed, pool_paths, gold_dens = args
    np.random.seed(seed_for(seed, db, gold) % (2**32))
    random.seed(seed_for(seed, db, gold))
    neighbors = generate_neighbor_queries_path(orig_path(db), gold)
    order_matters = "order by" in gold.lower()
    undist, strikes, chosen = set(neighbors), {}, []
    t0 = time.monotonic()
    for path in pool_paths:
        if not undist or time.monotonic() - t0 > QUERY_BUDGET_S:
            break
        g_den = gold_dens[path]
        hit = False
        for u in list(undist):
            flag, u_den = run_sql(path, u, NEIGHBOR_TIMEOUT_S)
            if flag == "timeout":
                strikes[u] = strikes.get(u, 0) + 1
                if strikes[u] >= MAX_STRIKES:
                    undist.discard(u)
                continue
            if flag == "result" and not result_eq(g_den, u_den, order_matters=order_matters):
                undist.discard(u)
                hit = True
        if hit:
            chosen.append(path)
    timed_out = sum(1 for v in strikes.values() if v >= MAX_STRIKES)
    return dict(db_id=db, gold=gold, n_neighbors=len(neighbors), n_undistinguished=len(undist),
                n_timeout_dropped=timed_out, chosen=chosen, secs=round(time.monotonic() - t0, 1))


def load_targets():
    golds = {}
    for f in SPLITS:
        for line in open(f):
            r = json.loads(line)
            golds.setdefault(r["db_id"], set()).add(r["gold"])
    dev = json.load(open(os.path.join(SPIDER, "dev.json")))
    fuzz_queries = {}
    for d in dev:
        fuzz_queries.setdefault(d["db_id"], set()).add(d["query"])
    return {db: sorted(g) for db, g in golds.items()}, {db: sorted(q) for db, q in fuzz_queries.items()}


def dir_bytes(path: str) -> int:
    return sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs)


def pool_index(path: str) -> int:
    return int(path.rsplit("pool", 1)[1].split(".")[0])


def build_db(db: str, golds: list, fuzz_queries: list, seed: int, workers: int) -> tuple[dict, list]:
    n_cand = LARGE_DB_CANDIDATES.get(db, DEFAULT_CANDIDATES)
    pool_dir = os.path.join(POOL, db)
    os.makedirs(pool_dir, exist_ok=True)
    os.makedirs(os.path.join(ORIG, db), exist_ok=True)
    shutil.copyfile(spider_path(db), orig_path(db))
    if os.path.getsize(orig_path(db)) > LARGE_ORIG_BYTES:
        workers = min(workers, 4)
    t0 = time.time()
    with mp.Pool(workers) as pool:
        gen = pool.map(make_pool_db, [(db, i, seed, fuzz_queries) for i in range(n_cand)])
        made = [os.path.join(pool_dir, f"{db}_pool{i}.sqlite") for _, i, st in gen if st == "ok"]
        checks = pool.map(check_pool_db, [(db, p, golds) for p in made])
        eligible = sorted((p for _, p, d in checks if d is not None), key=pool_index)
        dens = {p: d for _, p, d in checks if d is not None}
        t_gen = time.time()
        results = pool.map(distill, [(db, g, seed, eligible, {p: dens[p][g] for p in eligible}) for g in golds])
    chosen = sorted({p for r in results for p in r["chosen"]}, key=pool_index)
    out_dir = os.path.join(OUT, db)
    shutil.rmtree(out_dir, ignore_errors=True)
    os.makedirs(out_dir)
    shutil.copyfile(spider_path(db), os.path.join(out_dir, db + ".sqlite"))
    mapping = {}
    for k, p in enumerate(chosen, start=1):
        dst = os.path.join(out_dir, f"{db}{k}.sqlite")
        shutil.move(p, dst)
        mapping[os.path.basename(dst)] = os.path.basename(p)
    shutil.rmtree(pool_dir)  # delete every unselected candidate before the next db_id
    os.unlink(orig_path(db))
    info = dict(candidates=n_cand, workers=workers,
                status={st: sum(1 for *_, x in gen if x.startswith(st)) for st in ("ok", "too_big", "error")},
                eligible=len(eligible), suite_size=1 + len(chosen), n_golds=len(golds),
                suite_bytes=dir_bytes(out_dir), gen_check_s=round(t_gen - t0), distill_s=round(time.time() - t_gen),
                files=mapping)
    queries = [dict(r, chosen=[os.path.basename(p) for p in r["chosen"]]) for r in results]
    return info, queries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--dbs", nargs="*")
    args = ap.parse_args()
    if os.environ.get("PYTHONHASHSEED") != "0":
        sys.exit("set PYTHONHASHSEED=0 (the fuzzer iterates over sets of values)")
    golds, fuzz_queries = load_targets()
    oracle_dir = os.path.join(ROOT, "data", "oracle")
    manifest_path = os.path.join(oracle_dir, "manifest.json")
    manifest = {"seed": args.seed, "dbs": {}, "queries": []}
    if args.dbs and os.path.exists(manifest_path):  # incremental runs extend the manifest
        manifest = json.load(open(manifest_path))
        manifest["queries"] = [q for q in manifest["queries"] if q["db_id"] not in args.dbs]
    for db in args.dbs or sorted(golds):
        info, queries = build_db(db, golds[db], fuzz_queries[db], args.seed, args.workers)
        used = dir_bytes(oracle_dir)
        info["oracle_dir_bytes_after"] = used
        manifest["dbs"][db] = info
        manifest["queries"] += queries
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=1)
        left = sum(q["n_undistinguished"] for q in queries)
        print(f"{db}: suite={info['suite_size']} eligible={info['eligible']}/{info['candidates']} "
              f"status={info['status']} undistinguished={left} suite={info['suite_bytes'] / 2**20:.1f}MB "
              f"oracle_dir={used / 2**20:.0f}MB t={info['gen_check_s']}+{info['distill_s']}s", flush=True)
        if used > MAX_ORACLE_BYTES:
            sys.exit(f"ABORT: data/oracle is {used / 2**30:.2f} GB > 4 GB")


if __name__ == "__main__":
    main()
