"""Exploratory (not pre-registered): union-oracle sensitivity bound.

union oracle = test-suite oracle accepts AND pred matches gold on every usable generated DB
(original + each of the 24 candidates where gold executes). It reuses our own generator, so it is
NOT independent of the verifiers; it is reported only as a sensitivity bound.

Writes runs/exploratory/union_oracle/{summary.json, disagreements.jsonl, union_devA.jsonl, union_devB_<arm>.jsonl}.
Manual classifications are merged from runs/exploratory/union_oracle/manual_labels.json if present.
"""

import json
import shutil
import sqlite3
import os
import tempfile
from argparse import Namespace
from collections import Counter
from pathlib import Path

from xcommon import ARMS, KEYS, ROOT, accept, all_dbs, execute, load, qi, results_match  # sets sys.path

import analyze  # noqa: E402
from rewardshield.dbgen import read_schema  # noqa: E402

OUT = ROOT / "runs/exploratory/union_oracle"
MAX_SHOW = 8


def union(row: dict, suite) -> bool:
    return row["oracle"] and accept(row, all_dbs(suite))


def h_tests(rows: list[dict], label_key: str) -> dict:
    rs = [{**r, "oracle": r[label_key]} for r in rows]
    out = {"metrics": {k: analyze.verifier_metrics(rs, k) for k in KEYS}, "tests": {}}
    q = analyze._by(rs, "qid")
    for name, (a, b) in {"H1 targeted-4 vs single-1": ("single-1", "targeted-4"),
                         "H2 targeted-4 vs random-4": ("random-4", "targeted-4"),
                         "S1 targeted-4 vs random-16": ("random-16", "targeted-4")}.items():
        point, lo, hi = analyze.bootstrap(q, analyze.fa_share_diff(a, b))
        res = analyze.verdict_label(lo, hi, -1) if name[0] == "H" else ("within 1pt" if lo > -0.01 and hi < 0.01 else "not shown")
        out["tests"][name] = {"diff": point, "ci95": [lo, hi], "result": res}
    return out


# ---------- database integrity (declared constraints only) ----------

def _pk(table) -> list[str]:
    return [c.name for c in table.columns if c.pk]


def violations(db: str, tables) -> list[str]:
    """Declared-constraint violations: NULL/duplicate primary key, NULL in NOT NULL, dangling foreign key."""
    by = {t.name.lower(): t for t in tables}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    out = []
    try:
        for t in tables:
            pk = _pk(t)
            if pk:
                # identifiers quoted by the module's quoting helper; names come from local schema metadata only
                query = f"SELECT count(*) FROM {qi(t.name)} WHERE " + " OR ".join(f"{qi(c)} IS NULL" for c in pk)
                n = con.execute(query).fetchone()[0]
                if n:
                    out.append(f"{t.name}: {n} row(s) with NULL in primary key {pk}")
                cols = ", ".join(map(qi, pk))
                # identifiers quoted by the module's quoting helper; names come from local schema metadata only
                query = f"SELECT count(*) FROM (SELECT {cols} FROM {qi(t.name)} GROUP BY {cols} HAVING count(*) > 1)"
                n = con.execute(query).fetchone()[0]
                if n:
                    out.append(f"{t.name}: {n} duplicated primary key value(s) {pk}")
            for c in t.columns:
                if c.not_null and not c.pk:
                    # identifiers quoted by the module's quoting helper; names come from local schema metadata only
                    query = f"SELECT count(*) FROM {qi(t.name)} WHERE {qi(c.name)} IS NULL"
                    n = con.execute(query).fetchone()[0]
                    if n:
                        out.append(f"{t.name}.{c.name}: {n} NULL(s) in NOT NULL column")
            for col, parent, pcol in t.fks:
                p = by.get(parent.lower())
                pcol = pcol or (_pk(p)[0] if p and len(_pk(p)) == 1 else "")
                if not p or not pcol:
                    continue
                try:
                    # identifiers quoted by the module's quoting helper; names come from local schema metadata only
                    n = con.execute(f"SELECT count(*) FROM {qi(t.name)} WHERE {qi(col)} IS NOT NULL AND {qi(col)} NOT IN "
                                    f"(SELECT {qi(pcol)} FROM {qi(p.name)} WHERE {qi(pcol)} IS NOT NULL)").fetchone()[0]
                except sqlite3.Error:
                    continue
                if n:
                    out.append(f"{t.name}.{col} -> {p.name}.{pcol}: {n} dangling row(s)")
    finally:
        con.close()
    return out


def repaired_copy(db: str, tables) -> str:
    """Copy of db with rows violating declared constraints deleted (iterated to a fixpoint)."""
    by = {t.name.lower(): t for t in tables}
    fd, dst = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    shutil.copyfile(db, dst)
    con = sqlite3.connect(dst)
    changed = True
    while changed:
        changed = False
        for t in tables:
            pk = _pk(t)
            stmts = []
            if pk:
                stmts.append(f"DELETE FROM {qi(t.name)} WHERE " + " OR ".join(f"{qi(c)} IS NULL" for c in pk))
                cols = ", ".join(map(qi, pk))
                stmts.append(f"DELETE FROM {qi(t.name)} WHERE rowid NOT IN (SELECT min(rowid) FROM {qi(t.name)} GROUP BY {cols})")
            for col, parent, pcol in t.fks:
                p = by.get(parent.lower())
                pcol = pcol or (_pk(p)[0] if p and len(_pk(p)) == 1 else "")
                if p and pcol:
                    stmts.append(f"DELETE FROM {qi(t.name)} WHERE {qi(col)} IS NOT NULL AND {qi(col)} NOT IN "
                                 f"(SELECT {qi(pcol)} FROM {qi(p.name)} WHERE {qi(pcol)} IS NOT NULL)")
            for s in stmts:
                try:
                    changed |= con.execute(s).rowcount > 0
                except sqlite3.Error:
                    pass
        con.commit()
    con.close()
    return dst


def _show(res) -> object:
    if not res.ok:
        return {"error": res.error}
    rows = [list(r) for r in res.rows]
    return rows[:MAX_SHOW] + ([f"... {len(rows)} rows"] if len(rows) > MAX_SHOW else [])


def evidence(row: dict, suite, tables) -> dict:
    rej = [d for d in all_dbs(suite) if row["m"].get(d) is False]
    first = rej[0]
    # identifiers quoted by the module's quoting helper; names come from local schema metadata only
    g, p = suite.gold_results[first], execute(first, row["pred"])
    after = {}
    for d in rej:
        rd = repaired_copy(d, tables)
        gr, pr = execute(rd, row["gold"]), execute(rd, row["pred"])
        after[Path(d).name] = bool(gr.ok and pr.ok and results_match(gr.rows, pr.rows, suite.ordered))
        Path(rd).unlink()
    viol = {Path(d).name: violations(d, tables) for d in rej}
    return {"qid": row["qid"], "sample": row["sample"], "arm": row["arm"], "db_id": row["db_id"],
            "question": row["question"], "gold": row["gold"], "pred": row["pred"],
            "n_usable_dbs": sum(v is not None for v in row["m"].values()), "n_rejecting_dbs": len(rej),
            "rejecting_dbs": [Path(d).name for d in rej], "first_rejecting_db": Path(first).name,
            "gold_on_first": _show(g), "pred_on_first": _show(p),
            "violations_first": viol[Path(first).name],
            "original_db_violations": violations(suite.original_db, tables),
            "clean_rejecting_dbs": [k for k, v in viol.items() if not v],
            "matches_after_repair": after,
            "auto_hint": "b?" if all(after.values()) else "a/c? (still differs on a repaired DB)"}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    manual = {}
    mpath = OUT / "manual_labels.json"
    if mpath.exists():
        manual = json.loads(mpath.read_text())
    summary, dis = {"caveat": "Union oracle reuses our generator: not independent of the verifiers; sensitivity bound only."}, []
    schema = {}
    # dev-A
    rows, suites, _ = load("devA")
    rows_a = rows
    for r in rows:
        r["union"] = union(r, suites[r["qid"]])
    with open(OUT / "union_devA.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps({"qid": r["qid"], "sample": r["sample"], "db_id": r["db_id"], "oracle": r["union"]}) + "\n")
    summary["devA"] = {"n": len(rows), "oracle_true": sum(r["oracle"] for r in rows), "union_true": sum(r["union"] for r in rows),
                       "oracle": h_tests(rows, "oracle"), "union": h_tests(rows, "union")}
    for r in rows:
        if r["oracle"] and not r["union"]:
            s = suites[r["qid"]]
            tables = schema.setdefault(s.original_db, read_schema(s.original_db))
            dis.append({"split": "devA", **evidence(r, s, tables)})
    # dev-B
    rows, suites, _ = load("devB")
    for r in rows:
        r["union"] = union(r, suites[r["qid"]])
    summary["devB"] = {}
    for arm in ARMS:
        ar = [r for r in rows if r["arm"] == arm]
        with open(OUT / f"union_devB_{arm}.jsonl", "w") as f:
            for r in ar:
                f.write(json.dumps({"qid": r["qid"], "sample": 0, "db_id": r["db_id"], "oracle": r["union"]}) + "\n")
        summary["devB"][arm] = {"n": len(ar), "oracle_acc": sum(r["oracle"] for r in ar) / len(ar),
                                "union_acc": sum(r["union"] for r in ar) / len(ar),
                                "oracle_true_union_false": sum(r["oracle"] and not r["union"] for r in ar)}
    orig = lambda arm: str(ROOT / f"runs/E04/out/{arm}_devB_oracle.jsonl")
    uni = lambda arm: str(OUT / f"union_devB_{arm}.jsonl")
    summary["devB_H3"] = {"oracle": analyze.cli_arms(Namespace(a=orig("E04"), b=orig("E05"))),
                          "union": analyze.cli_arms(Namespace(a=uni("E04"), b=uni("E05")))}
    for r in rows:
        if r["oracle"] and not r["union"]:
            s = suites[r["qid"]]
            tables = schema.setdefault(s.original_db, read_schema(s.original_db))
            dis.append({"split": "devB", **evidence(r, s, tables)})
    # merge manual labels, keyed by split|qid|arm|sample
    for d in dis:
        lab = manual.get(f"{d['split']}|{d['qid']}|{d['arm']}|{d['sample']}") or manual.get(f"{d['split']}|{d['qid']}|*")
        d["class"], d["class_note"] = (lab or [None, None])[:2]
    with open(OUT / "disagreements.jsonl", "w") as f:
        for d in dis:
            f.write(json.dumps(d, default=str) + "\n")
    # narrower sensitivity: flip oracle-correct rows to wrong only for the manually classified categories
    cls = {(d["qid"], d["sample"]): d["class"] for d in dis if d["split"] == "devA"}
    for name, flip in (("oracle_plus_class_a", {"a_genuine_counterexample"}),
                       ("oracle_plus_class_a_and_c", {"a_genuine_counterexample", "c_ambiguity"})):
        for r in rows_a:
            r[name] = r["oracle"] and cls.get((r["qid"], r["sample"])) not in flip
        summary["devA"][name] = h_tests(rows_a, name)
    summary["disagreements"] = {
        sp: {"samples": sum(d["split"] == sp for d in dis), "questions": len({d["qid"] for d in dis if d["split"] == sp}),
             "distinct_qid_sql": len({(d["qid"], " ".join(d["pred"].lower().split())) for d in dis if d["split"] == sp}),
             "auto_hint": dict(Counter(d["auto_hint"] for d in dis if d["split"] == sp)),
             "class": dict(Counter(str(d["class"]) for d in dis if d["split"] == sp))}
        for sp in ("devA", "devB")}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: summary[k] for k in ("disagreements",)}, indent=1))


if __name__ == "__main__":
    main()
