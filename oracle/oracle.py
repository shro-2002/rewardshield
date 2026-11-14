"""Independent test-suite oracle for Spider dev (see oracle/ORACLE.md).

oracle_match(db_id, gold, pred) -> True / False / None (None = cannot judge).
Judging is done by the vendored official evaluator
third_party/test-suite-sql-eval/exec_eval.py::eval_exec_match over the regenerated
suite in data/oracle/test_suite/<db_id>/ with keep_distinct=True, plug_value=False.

CLI: python oracle/oracle.py --pairs pairs.jsonl --out verdicts.jsonl [--workers 8]
     each input line: {"qid", "db_id", "gold", "pred"}
"""
import argparse
import json
import multiprocessing as mp
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUITE_DIR = os.path.join(ROOT, "data", "oracle", "test_suite")
sys.path.insert(0, os.path.join(ROOT, "third_party", "test-suite-sql-eval"))
import exec_eval  # noqa: E402  (official evaluator, unmodified)

QUERY_TIMEOUT_S = 10.0  # per query per database


_DENIED = {sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE,
           sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE, sqlite3.SQLITE_ALTER_TABLE,
           sqlite3.SQLITE_CREATE_INDEX, sqlite3.SQLITE_DROP_INDEX, sqlite3.SQLITE_CREATE_VIEW, sqlite3.SQLITE_DROP_VIEW,
           sqlite3.SQLITE_CREATE_TRIGGER, sqlite3.SQLITE_DROP_TRIGGER, sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_PRAGMA}


def _cursor_with_deadline(sqlite_path: str):
    # Predictions are model-written, so suite databases are opened read-only with an authorizer
    # that denies writes, DDL, ATTACH and PRAGMA; this replaces the official writable connect.
    # The official exec_on_db timeout (asyncio.wait_for around blocking code) never fires,
    # so a sqlite progress-handler deadline is added. An interrupted or denied query surfaces
    # as ("exception", ...) exactly like any other execution error.
    connection = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
    connection.text_factory = lambda b: b.decode(errors="ignore")
    connection.set_authorizer(lambda action, *_: sqlite3.SQLITE_DENY if action in _DENIED else sqlite3.SQLITE_OK)
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 100_000)
    deadline = time.monotonic() + QUERY_TIMEOUT_S
    connection.set_progress_handler(lambda: time.monotonic() > deadline, 10000)
    return connection.cursor()


_cursor_with_deadline.__wrapped__ = exec_eval.get_cursor_from_path
exec_eval.get_cursor_from_path = _cursor_with_deadline


def oracle_match(db_id: str, gold: str, pred: str) -> bool | None:
    db_path = os.path.join(SUITE_DIR, db_id, db_id + ".sqlite")
    if not os.path.exists(db_path):
        return None
    if not pred or not pred.strip():
        return False
    try:
        return bool(exec_eval.eval_exec_match(db_path, pred, gold, plug_value=False,
                                              keep_distinct=True, progress_bar_for_each_datapoint=False))
    except AssertionError:  # gold failed on a suite database: cannot judge
        return None
    except (sqlite3.Error, ValueError, TypeError, RecursionError):
        return None


def _judge(row: dict) -> dict:
    t0 = time.monotonic()
    verdict = oracle_match(row["db_id"], row["gold"], row["pred"])
    return {"qid": row.get("qid"), "db_id": row["db_id"], "verdict": verdict,
            "secs": round(time.monotonic() - t0, 3)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args()
    rows = [json.loads(line) for line in open(args.pairs) if line.strip()]
    if args.workers > 1:
        with mp.Pool(args.workers) as pool:
            verdicts = pool.map(_judge, rows, chunksize=4)
    else:
        verdicts = [_judge(r) for r in rows]
    with open(args.out, "w") as f:
        for v in verdicts:
            f.write(json.dumps(v) + "\n")
    counts = {str(k): sum(v["verdict"] is k for v in verdicts) for k in (True, False, None)}
    print(json.dumps({"n": len(verdicts), **counts}))


if __name__ == "__main__":
    main()
