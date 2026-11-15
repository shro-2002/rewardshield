"""Exploratory: blind human-label validation set (~60 rows) for the project owner.

Strata (seed 20261115):
  claude_disagreement  20 dev-A rows from the 89 Claude-labelled disagreement rows (runs/E03/labels_devA.jsonl)
  all_accept           20 dev-A rows drawn uniformly from samples every verifier AND the oracle accept
  oracle_rej_single_acc 10 dev-A rows the oracle rejects but single-1 accepts (not already drawn above)
  devB_arms            10 dev-B rows from E04/E05 greedy outputs, 4 of them flight_2
Rows without SQL are excluded; one row per distinct (question, normalised SQL). The CSV/MD carry no
verdicts, labels, strata, model names or sample ids; the mapping lives in key.jsonl.
"""

import csv
import json
import random
import sqlite3

from xcommon import read_jsonl, KEYS, ROOT, load

OUT = ROOT / "runs/exploratory/blind_labels"
SEED = 20261115
FIELDS = ["row_id", "db_id", "schema", "question", "gold_sql", "predicted_sql", "label", "notes"]

INSTRUCTIONS = """# Blind SQL equivalence labels

Exploratory validation set (not pre-registered). For each row, decide whether the predicted SQL answers
the question the same way as the gold SQL. Fill in `label` in `to_label.csv` (this file is a readable copy).

- `equivalent`: the two queries return the same result on **every valid database state consistent with the
  schema** (keys unique and non-NULL, foreign keys pointing at existing rows, NOT NULL respected; nullable
  columns may be NULL; tables may be empty). Column order and alias names do not matter; row order matters only
  if the gold query has a top-level ORDER BY.
- `not_equivalent`: there is some valid database state where the results differ, and the difference is not
  explained by an ambiguity in the question.
- `ambiguous`: the question admits both readings (e.g. ties, NULL handling, whether an unmatched nullable
  foreign key row should count, 'courses' vs 'course assignments'), so either query is a defensible answer.

Use `notes` for a one-line reason, especially for `not_equivalent` (the kind of database state that separates
them) and `ambiguous` (the two readings). Do not run the queries against the Spider data to decide; the
question is about all valid states, not the one shipped database. Rows are in random order; nothing about
their source is shown on purpose.

"""


def schema_sql(db_path: str) -> str:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    ddl = [r[0].strip() for r in con.execute("SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL "
                                             "AND name NOT LIKE 'sqlite_%'")]
    con.close()
    return ";\n".join(ddl) + ";"


def norm(sql: str) -> str:
    return " ".join(sql.lower().split())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    rows_a, _, qa = load("devA")
    rows_b, _, qb = load("devB")
    claude = {(r["qid"], r["sample"]): r for r in read_jsonl("runs/E03/labels_devA.jsonl")}
    union = {(r["qid"], r["sample"]): r["oracle"] for r in read_jsonl("runs/exploratory/union_oracle/union_devA.jsonl")}
    seen, picked = set(), []

    def take(pool: list[dict], n: int, stratum: str) -> None:
        pool = sorted(pool, key=lambda r: (r["qid"], r["arm"], r["sample"]))
        rng.shuffle(pool)
        got = 0
        for r in pool:
            k = (r["qid"], norm(r["pred"]))
            if got == n or k in seen:
                continue
            seen.add(k)
            picked.append((stratum, r))
            got += 1
        assert got == n, f"{stratum}: only {got} of {n}"

    has = [r for r in rows_a if r["has"]]
    take([r for r in has if (r["qid"], r["sample"]) in claude], 20, "claude_disagreement")
    take([r for r in has if r["oracle"] and all(r["verdict"][k] for k in KEYS)], 20, "all_accept")
    take([r for r in has if not r["oracle"] and r["verdict"]["single-1"]], 10, "oracle_rej_single_acc")
    hb = [r for r in rows_b if r["has"] and r["arm"] in ("E04", "E05")]
    take([r for r in hb if r["db_id"] == "flight_2"], 4, "devB_arms")
    take([r for r in hb if r["db_id"] != "flight_2"], 6, "devB_arms")

    ids = rng.sample(range(100, 1000), len(picked))
    rng.shuffle(picked)
    out_rows, keys = [], []
    for rid, (stratum, r) in zip(ids, picked):
        q = (qa if r["arm"] == "pool" else qb)[r["qid"]]
        row_id = f"R{rid}"
        out_rows.append({"row_id": row_id, "db_id": r["db_id"], "schema": schema_sql(q["db_path"]), "question": r["question"],
                         "gold_sql": r["gold"], "predicted_sql": r["pred"].strip(), "label": "", "notes": ""})
        c = claude.get((r["qid"], r["sample"])) if r["arm"] == "pool" else None
        keys.append({"row_id": row_id, "stratum": stratum, "split": "devA" if r["arm"] == "pool" else "devB",
                     "source": "runs/E02/pool_devA.jsonl" if r["arm"] == "pool" else f"runs/E04/out/{r['arm']}_devB.jsonl",
                     "qid": r["qid"], "sample": r["sample"], "arm": r["arm"], "db_id": r["db_id"],
                     "oracle": r["oracle"], "union_oracle": union.get((r["qid"], r["sample"])) if r["arm"] == "pool" else None,
                     "verdicts": r["verdict"], "claude_label": c["label"] if c else None,
                     "claude_category": c.get("category") if c else None})
    with open(OUT / "to_label.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(out_rows)
    with open(OUT / "key.jsonl", "w") as f:
        for k in keys:
            f.write(json.dumps(k) + "\n")
    md = [INSTRUCTIONS]
    for r in out_rows:
        md += [f"## {r['row_id']} ({r['db_id']})", "", f"**Question:** {r['question']}", "",
               "<details><summary>Schema</summary>", "", "```sql", r["schema"], "```", "", "</details>", "",
               "**Gold SQL**", "", "```sql", r["gold_sql"], "```", "", "**Predicted SQL**", "", "```sql", r["predicted_sql"], "```", "",
               "label: ______ (equivalent / not_equivalent / ambiguous)  ", "notes: ", ""]
    (OUT / "to_label.md").write_text("\n".join(md))
    from collections import Counter
    print(len(out_rows), dict(Counter(k["stratum"] for k in keys)), "claude-labelled:", sum(k["claude_label"] is not None for k in keys))


if __name__ == "__main__":
    main()
