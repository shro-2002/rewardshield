"""Exploratory (not pre-registered): degenerate-gold blind spot (flight_2 and elsewhere).

A gold result is "degenerate" on a database when it is empty, or every value is 0 / NULL
(e.g. COUNT(*) = 0, AVG over nothing = NULL). Checked on the original Spider DB, every oracle
test-suite DB and our 24 generated candidates. Counts false accepts that fall on such questions,
per verifier and per model, and re-reports dev-B numbers with and without them (sensitivity only;
the benchmark is unchanged). Writes runs/exploratory/flight2/{report.json, questions.jsonl, devB_*_filtered.jsonl}.
"""

import json
import os
import re
import shutil
import sqlite3
import tempfile
from argparse import Namespace
from collections import Counter, defaultdict
from pathlib import Path

from xcommon import ARMS, KEYS, ROOT, execute, load, qi  # sets sys.path

import analyze  # noqa: E402
from rewardshield.sqlexec import literals  # noqa: E402

OUT = ROOT / "runs/exploratory/flight2"
SUITE = ROOT / "data/oracle/test_suite"


def kind(res) -> str:
    if not res.ok:
        return "error"
    if not res.rows:
        return "empty"
    vals = [v for r in res.rows for v in r]
    if all(v is None for v in vals):
        return "all_null"
    if all(v is None or v == 0 for v in vals):
        return "all_zero"
    return "ok"


def oracle_dbs(db_id: str) -> list[Path]:
    return sorted((SUITE / db_id).glob("*.sqlite"))


def question_table(split: str, suites: dict, qs: dict) -> dict:
    out = {}
    for qid, s in suites.items():
        q = qs[qid]
        orc = [kind(execute(str(p), q["gold"])) for p in oracle_dbs(q["db_id"])]
        cand = [kind(s.gold_results[c]) for c in s.candidates]
        out[qid] = {"split": split, "qid": qid, "db_id": q["db_id"], "question": q["question"], "gold": q["gold"],
                    "original": kind(s.gold_results[s.original_db]),
                    "oracle_kinds": dict(Counter(orc)), "n_oracle_dbs": len(orc),
                    "candidate_kinds": dict(Counter(cand)),
                    "empty_on_all_oracle": all(k == "empty" for k in orc),
                    "degenerate_on_all_oracle": all(k != "ok" for k in orc)}
        out[qid]["degenerate_original"] = out[qid]["original"] != "ok"
    return out


def whitespace_profile(db: str) -> dict:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    prof = {}
    # Table/column names come only from sqlite_master/PRAGMA of local read-only databases; quoted via qi().
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'"):
        for col in [r[1] for r in con.execute("SELECT * FROM pragma_table_info(?)", (t,))]:
            c, padded_expr = qi(col), f"typeof({qi(col)})='text' AND {qi(col)} != trim({qi(col)})"
            # identifiers quoted by qi(), names from local PRAGMA only
            query = f"SELECT count({c}), sum({padded_expr}) FROM {qi(t)}"
            n, padded = con.execute(query).fetchone()
            if padded:
                # identifiers quoted by qi(), names from local PRAGMA only
                query = f"SELECT {c} FROM {qi(t)} WHERE {padded_expr} LIMIT 3"
                ex = con.execute(query).fetchall()
                prof[f"{t}.{col}"] = {"non_null": n, "padded": padded, "examples": [repr(e[0]) for e in ex]}
    joins = {"flights.SourceAirport = airports.AirportCode": "SELECT count(*) FROM flights f JOIN airports a ON f.SourceAirport = a.AirportCode",
             "flights.DestAirport = airports.AirportCode": "SELECT count(*) FROM flights f JOIN airports a ON f.DestAirport = a.AirportCode",
             "flights.Airline = airlines.uid": "SELECT count(*) FROM flights f JOIN airlines a ON f.Airline = a.uid",
             "rows in flights": "SELECT count(*) FROM flights"}
    prof["_join_rows"] = {k: con.execute(v).fetchone()[0] for k, v in joins.items()} if "flight" in db else {}
    con.close()
    return prof


def fa_counts(rows: list[dict], degen: set, dedup: bool) -> dict:
    if dedup:  # one row per distinct (question, normalised SQL), as in the auditor's audit5
        seen, kept = set(), []
        for r in rows:
            k = (r["qid"], " ".join((r["pred"] or "").lower().split()))
            if k not in seen:
                seen.add(k)
                kept.append(r)
        rows = kept
    out = {}
    for k in KEYS:
        acc = [r for r in rows if r["verdict"][k]]
        fa = [r for r in acc if not r["oracle"]]
        fa_d = [r for r in fa if r["qid"] in degen]
        acc_nd = [r for r in acc if r["qid"] not in degen]
        out[k] = {"accepts": len(acc), "FA": len(fa), "FA_on_degenerate_q": len(fa_d),
                  "FA_flight_2": sum(r["db_id"] == "flight_2" for r in fa),
                  "FA_share": len(fa) / len(acc), "FA_share_without_degenerate_q": (len(fa) - len(fa_d)) / len(acc_nd)}
    return {"n_rows": len(rows), "by_verifier": out}


def trimmed_copy(src: str) -> str:
    """Copy of src with every text value stripped of surrounding whitespace (to test the whitespace cause)."""
    fd, dst = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    shutil.copyfile(src, dst)
    con = sqlite3.connect(dst)
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
        for col in [r[1] for r in con.execute("SELECT * FROM pragma_table_info(?)", (t,)).fetchall()]:
            c = qi(col)
            # identifiers quoted by qi(), names from local PRAGMA only
            query = f"UPDATE {qi(t)} SET {c} = trim({c}) WHERE typeof({c}) = 'text'"
            con.execute(query)
    con.commit()
    con.close()
    return dst


def causes(table: dict, rows: list[dict], degen: set) -> dict:
    """Why flight_2 golds are degenerate, and which dev-B false accepts sit on those questions."""
    orig = str(ROOT / "data/raw/spider_zip/spider/database/flight_2/flight_2.sqlite")
    trimmed = trimmed_copy(orig)
    f2 = [t for t in table.values() if t["db_id"] == "flight_2" and t["degenerate_original"]]
    fixed = {t["qid"]: kind(execute(trimmed, t["gold"])) for t in f2}
    Path(trimmed).unlink()
    lit_lost = {t["qid"]: (literals(t["gold"]), bool(re.search(r'"[^"]*"', t["gold"]))) for t in f2}
    all_q = list(table.values())
    seen, dedup = set(), []
    for r in rows:
        k = (r["qid"], " ".join((r["pred"] or "").lower().split()))
        if k not in seen:
            seen.add(k)
            dedup.append(r)
    f2deg = {t["qid"] for t in f2}
    fa_tab = {}
    for name, rs in (("all_rows", rows), ("dedup", dedup)):
        fa_tab[name] = {k: {"FA": sum(r["verdict"][k] and not r["oracle"] for r in rs),
                            "FA_flight_2": sum(r["verdict"][k] and not r["oracle"] and r["db_id"] == "flight_2" for r in rs),
                            "FA_flight_2_degenerate_gold": sum(r["verdict"][k] and not r["oracle"] and r["qid"] in f2deg for r in rs),
                            "FA_other_degenerate_gold": sum(r["verdict"][k] and not r["oracle"] and r["qid"] in degen - f2deg for r in rs)}
                        for k in KEYS}
    per_arm = {a: {k: sum(r["verdict"][k] and not r["oracle"] and r["qid"] in f2deg for r in rows if r["arm"] == a) for k in KEYS} for a in ARMS}
    return {"flight_2_degenerate_questions": len(f2),
            "gold_kind_after_trimming_whitespace": dict(Counter(fixed.values())),
            "still_degenerate_after_trim": [q for q, v in fixed.items() if v != "ok"],
            "double_quoted_string_literal_in_gold_not_seeded": sum(1 for lits, dq in lit_lost.values() if dq and not any(isinstance(x, str) for x in lits)),
            "all_golds_with_double_quoted_literal": sum(bool(re.search(r'=\s*"|LIKE\s*"|IN\s*\(\s*"', t["gold"], re.I)) for t in all_q),
            "all_24_candidates_degenerate_flight_2": sum(t["candidate_kinds"].get("ok", 0) == 0 for t in f2),
            "devB_FA_on_flight_2_degenerate": fa_tab, "devB_FA_flight_2_degenerate_per_arm": per_arm}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"definition": "degenerate = gold result empty, or every value 0/NULL",
              "note": "Exploratory sensitivity analysis; benchmark and exclusions unchanged."}
    table, data = {}, {}
    for sp in ("devA", "devB"):
        rows, suites, qs = load(sp)
        data[sp] = rows
        table.update(question_table(sp, suites, qs))
    with open(OUT / "questions.jsonl", "w") as f:
        for t in table.values():
            f.write(json.dumps(t) + "\n")
    for sp in ("devA", "devB"):
        ts = [t for t in table.values() if t["split"] == sp]
        by_db = defaultdict(Counter)
        for t in ts:
            by_db[t["db_id"]]["questions"] += 1
            by_db[t["db_id"]]["degenerate_original"] += t["degenerate_original"]
            by_db[t["db_id"]]["degenerate_on_all_oracle"] += t["degenerate_on_all_oracle"]
            by_db[t["db_id"]]["empty_on_all_oracle"] += t["empty_on_all_oracle"]
        report[sp] = {"questions": len(ts),
                      "original_kind": dict(Counter(t["original"] for t in ts)),
                      "degenerate_original": sum(t["degenerate_original"] for t in ts),
                      "degenerate_on_all_oracle": sum(t["degenerate_on_all_oracle"] for t in ts),
                      "empty_on_all_oracle (pre-registered exclusion)": sum(t["empty_on_all_oracle"] for t in ts),
                      "degenerate_original_by_db": {d: dict(c) for d, c in sorted(by_db.items()) if c["degenerate_original"] or c["degenerate_on_all_oracle"]},
                      "degenerate_questions": [{k: t[k] for k in ("qid", "db_id", "gold", "original", "oracle_kinds", "candidate_kinds")}
                                               for t in ts if t["degenerate_original"] or t["degenerate_on_all_oracle"]]}
    report["whitespace_flight_2_original"] = whitespace_profile(str(ROOT / "data/raw/spider_zip/spider/database/flight_2/flight_2.sqlite"))
    report["whitespace_flight_2_oracle_dbs"] = {p.name: {k: v["padded"] for k, v in whitespace_profile(str(p)).items() if not k.startswith("_")}
                                                for p in oracle_dbs("flight_2")}
    # false accepts and sensitivity on dev-B
    degen = {q for q, t in table.items() if t["degenerate_original"]}
    rows = data["devB"]
    report["devB_FA"] = {"pooled_all_rows": fa_counts(rows, degen, False), "pooled_dedup": fa_counts(rows, degen, True),
                         "per_arm": {a: fa_counts([r for r in rows if r["arm"] == a], degen, False) for a in ARMS}}
    report["devA_FA"] = fa_counts(data["devA"], degen, False)
    sens = {}
    for a in ARMS:
        ar = [r for r in rows if r["arm"] == a]
        keep = [r for r in ar if r["qid"] not in degen]
        sens[a] = {"acc_all": sum(r["oracle"] for r in ar) / len(ar), "n_all": len(ar),
                   "acc_without_degenerate": sum(r["oracle"] for r in keep) / len(keep), "n_without": len(keep),
                   "correct_on_degenerate": sum(r["oracle"] for r in ar if r["qid"] in degen)}
        with open(OUT / f"devB_{a}_filtered.jsonl", "w") as f:
            for r in keep:
                f.write(json.dumps({"qid": r["qid"], "sample": 0, "db_id": r["db_id"], "oracle": r["oracle"]}) + "\n")
    sens["H3_without_degenerate"] = analyze.cli_arms(Namespace(a=str(OUT / "devB_E04_filtered.jsonl"), b=str(OUT / "devB_E05_filtered.jsonl")))
    report["devB_sensitivity"] = sens
    report["causes"] = causes(table, rows, degen)
    excl = {q for q, t in table.items() if t["empty_on_all_oracle"]}
    pre = {"questions": sorted(excl)}
    for a in ARMS:
        keep = [r for r in rows if r["arm"] == a and r["qid"] not in excl]
        pre[a] = {"acc": sum(r["oracle"] for r in keep) / len(keep), "n": len(keep),
                  "oracle_true_on_excluded": sum(r["oracle"] for r in rows if r["arm"] == a and r["qid"] in excl)}
        with open(OUT / f"devB_{a}_preexcl.jsonl", "w") as f:
            for r in keep:
                f.write(json.dumps({"qid": r["qid"], "sample": 0, "db_id": r["db_id"], "oracle": r["oracle"]}) + "\n")
    pre["H3"] = analyze.cli_arms(Namespace(a=str(OUT / "devB_E04_preexcl.jsonl"), b=str(OUT / "devB_E05_preexcl.jsonl")))
    report["preregistered_exclusion_empty_on_every_oracle_db"] = pre
    (OUT / "report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: report[k] for k in ("devA", "devB")}, indent=1, default=str)[:6000])


if __name__ == "__main__":
    main()
