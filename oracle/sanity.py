"""Sanity checks for the oracle (numbers go into oracle/ORACLE.md).

(a) every devA/devB gold matches itself
(b) 50 rule-made wrong variants of devA golds: share rejected by the oracle
    (and, for comparison, by plain execution match on the original Spider DB only)
(c) informativeness: share of golds whose denotation differs across >= 2 suite DBs

Run: oracle/.venv/bin/python oracle/sanity.py
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from oracle import ROOT, SUITE_DIR, exec_eval, oracle_match  # noqa: E402

SPLITS = {s: os.path.join(ROOT, "data", "splits", f"{s}.jsonl") for s in ("devA", "devB")}
TABLES = json.load(open(os.path.join(ROOT, "data", "raw", "spider_zip", "spider", "tables.json")))
OUT_DIR = os.path.join(ROOT, "oracle", "sanity_out")
N_MUTANTS, PER_RULE = 50, 9


def rows(split: str) -> list[dict]:
    return [json.loads(line) for line in open(SPLITS[split])]


def non_pk_column(db_id: str, table: str) -> str | None:
    schema = next(t for t in TABLES if t["db_id"] == db_id)
    names = [n.lower() for n in schema["table_names_original"]]
    if table.lower() not in names:
        return None
    t_idx = names.index(table.lower())
    for c_idx, (t, col) in enumerate(schema["column_names_original"]):
        if t == t_idx and c_idx not in schema["primary_keys"]:
            return col
    return None


def m_drop_where(q, db):
    m = re.search(r"\s+AND\s+[^()]+?(?=\s+(GROUP|ORDER|LIMIT|INTERSECT|UNION|EXCEPT)\b|\s*$)", q, re.I)
    if m and "between" not in q[:m.start()].lower().split("where")[-1]:
        return q[:m.start()] + q[m.end():]
    m = re.search(r"\s+WHERE\s+[^()]+?(?=\s+(GROUP|ORDER|LIMIT)\b|\s*$)", q, re.I)
    if m and q.lower().count("select") == 1:
        return q[:m.start()] + q[m.end():]
    return None


def m_flip_cmp(q, db):
    for a, b in ((r"\s>\s", " >= "), (r"\s<\s", " <= "), (r"\s>=\s", " > "), (r"\s<=\s", " < ")):
        if re.search(a, q):
            return re.sub(a, b, q, count=1)
    return None


def m_count_distinct(q, db):
    m = re.search(r"count\s*\(\s*\*\s*\)", q, re.I)
    tables = re.findall(r"\bFROM\s+(\w+)", q, re.I)
    if not m or len(tables) != 1 or re.search(r"\bJOIN\b", q, re.I):
        return None
    col = non_pk_column(db, tables[0])
    return q[:m.start()] + f"count(DISTINCT {col})" + q[m.end():] if col else None


def m_flip_order(q, db):
    if re.search(r"\bDESC\b", q, re.I):
        return re.sub(r"\bDESC\b", "ASC", q, count=1, flags=re.I)
    if re.search(r"ORDER BY", q, re.I) and re.search(r"\bLIMIT\b", q, re.I):
        return re.sub(r"(\s+LIMIT\b)", r" DESC\1", q, count=1, flags=re.I)
    return None


def m_agg_swap(q, db):
    for a, b in (("max(", "min("), ("min(", "max("), ("avg(", "sum("), ("sum(", "avg(")):
        i = q.lower().find(a)
        if i >= 0:
            return q[:i] + b + q[i + len(a):]
    return None


def m_and_or(q, db):
    if re.search(r"\bBETWEEN\b", q, re.I):
        return None
    return re.sub(r"\bAND\b", "OR", q, count=1, flags=re.I) if re.search(r"\bAND\b", q, re.I) else None


def m_set_op(q, db):
    for a, b in (("INTERSECT", "UNION"), ("EXCEPT", "INTERSECT"), ("UNION", "INTERSECT"), ("NOT IN", "IN")):
        if re.search(rf"\b{a}\b", q, re.I):
            return re.sub(rf"\b{a}\b", b, q, count=1, flags=re.I)
    return None


def m_drop_distinct(q, db):
    return re.sub(r"\bDISTINCT\s+", "", q, count=1, flags=re.I) if re.search(r"\bDISTINCT\b", q, re.I) else None


RULES = [m_drop_where, m_flip_cmp, m_count_distinct, m_flip_order, m_agg_swap, m_and_or, m_set_op,
         m_drop_distinct]


def make_mutants() -> list[dict]:
    golds, seen = [], set()
    for r in rows("devA"):
        if (r["db_id"], r["gold"]) not in seen:
            seen.add((r["db_id"], r["gold"]))
            golds.append(r)
    used = {f.__name__: 0 for f in RULES}
    mutants = []
    for k, r in enumerate(golds):
        for j in range(len(RULES)):  # rotate the starting rule for a balanced mix
            rule = RULES[(k + j) % len(RULES)]
            if used[rule.__name__] >= PER_RULE:
                continue
            q = rule(r["gold"], r["db_id"])
            if q and q.strip() != r["gold"].strip():
                orig = os.path.join(SUITE_DIR, r["db_id"], r["db_id"] + ".sqlite")
                if exec_eval.asyncio.run(exec_eval.exec_on_db(orig, q))[0] == "result":
                    used[rule.__name__] += 1
                    mutants.append(dict(qid=r["qid"], db_id=r["db_id"], gold=r["gold"], pred=q,
                                        rule=rule.__name__))
                    break
        if len(mutants) == N_MUTANTS:
            break
    return mutants


def original_db_match(db_id: str, gold: str, pred: str) -> bool:
    path = os.path.join(SUITE_DIR, db_id, db_id + ".sqlite")
    g = exec_eval.asyncio.run(exec_eval.exec_on_db(path, gold))
    p = exec_eval.asyncio.run(exec_eval.exec_on_db(path, pred))
    return p[0] == "result" and exec_eval.result_eq(g[1], p[1], order_matters="order by" in gold.lower())


def informative(db_id: str, gold: str) -> bool:
    d = os.path.join(SUITE_DIR, db_id)
    dens = [exec_eval.asyncio.run(exec_eval.exec_on_db(os.path.join(d, f), gold))[1]
            for f in sorted(os.listdir(d)) if f.endswith(".sqlite")]
    om = "order by" in gold.lower()
    return any(not exec_eval.result_eq(dens[0], x, order_matters=om) for x in dens[1:])


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    report = {}
    all_rows = rows("devA") + rows("devB")
    t0 = time.monotonic()
    self_v = [oracle_match(r["db_id"], r["gold"], r["gold"]) for r in all_rows]
    report["a_self_match"] = dict(n=len(all_rows), true=self_v.count(True), false=self_v.count(False),
                                  none=self_v.count(None),
                                  failures=[r["qid"] for r, v in zip(all_rows, self_v) if v is not True],
                                  secs_per_pair=round((time.monotonic() - t0) / len(all_rows), 4))
    mutants = make_mutants()
    for m in mutants:
        m["oracle"] = oracle_match(m["db_id"], m["gold"], m["pred"])
        m["orig_db_match"] = original_db_match(m["db_id"], m["gold"], m["pred"])
    with open(os.path.join(OUT_DIR, "mutants.jsonl"), "w") as f:
        for m in mutants:
            f.write(json.dumps(m) + "\n")
    by_rule = {}
    for m in mutants:
        s = by_rule.setdefault(m["rule"], [0, 0])
        s[0] += 1
        s[1] += m["oracle"] is False
    report["b_mutants"] = dict(n=len(mutants), oracle_rejected=sum(m["oracle"] is False for m in mutants),
                               oracle_none=sum(m["oracle"] is None for m in mutants),
                               orig_db_rejected=sum(not m["orig_db_match"] for m in mutants),
                               by_rule_n_rejected=by_rule,
                               accepted=[(m["qid"], m["rule"], m["pred"]) for m in mutants if m["oracle"]])
    uniq = sorted({(r["db_id"], r["gold"]) for r in all_rows})
    info = {u: informative(*u) for u in uniq}
    report["c_informative"] = dict(unique_golds=len(uniq), informative=sum(info.values()),
                                   questions=len(all_rows),
                                   questions_informative=sum(info[(r["db_id"], r["gold"])] for r in all_rows),
                                   uninformative=[g for (d, g), v in info.items() if not v])
    with open(os.path.join(OUT_DIR, "report.json"), "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps({k: {x: y for x, y in v.items() if not isinstance(y, list)} for k, v in report.items()},
                     indent=1))


if __name__ == "__main__":
    main()
