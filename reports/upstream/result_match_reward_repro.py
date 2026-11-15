"""Minimal repro: limits of AgentTune's built-in result_match_reward (agenttune 1.1.5, same code on main).

Self-contained: needs only agenttune and stdlib sqlite3 (temp databases, temp working directory).
Every claim printed below is asserted; the script exits non-zero if one does not hold.
    python reports/upstream/result_match_reward_repro.py
    python reports/upstream/result_match_reward_repro.py --tokenizer ~/models/tiny-aya-global  # real Tiny Aya template
"""

import argparse
import json
import os
import sqlite3
import tempfile
import warnings

warnings.simplefilter("ignore")
WORKDIR = tempfile.mkdtemp(prefix="rmr-repro-")
os.chdir(WORKDIR)  # result_match_reward logs to ./data/scores.jsonl; keep that out of the caller's tree

from agenttune.agentic.rewards.builtin_rewards.sql import result_match_reward  # noqa: E402
from agenttune.agentic.rollout_engines.base import RolloutEngine  # noqa: E402
from agenttune.agentic.rollout_engines.rollout_factory import create_rollout_fn  # noqa: E402

SCHEMA = """
CREATE TABLE singer (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, country TEXT, fee REAL, tax REAL, bonus REAL);
INSERT INTO singer VALUES (1,'Ana',25,'Peru',0.1,0.2,0.3),(2,'Bo',41,'Chile',1.0,2.0,3.0),
                          (3,'Cy',35,'Peru',0.5,0.25,0.25),(4,'Di',19,NULL,1.0,1.0,1.0);
"""
SECOND_DB_EXTRA = "INSERT INTO singer VALUES (5,'Ed',30,'Peru',1.0,1.0,1.0);"  # an age exactly at the boundary


def make_db(extra: str = "") -> str:
    path = os.path.join(WORKDIR, f"db{abs(hash(extra))}.sqlite")
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA + extra)
    return path


def rows(db: str, sql: str):
    with sqlite3.connect(db) as conn:
        try:
            return conn.execute(sql).fetchall()
        except sqlite3.Error as exc:
            return {"error": str(exc)}


def conversation(db: str, *sqls: str) -> list[dict]:
    """AgentTune's native rollout shape: assistant tool call, then a "tool" turn holding str(result)."""
    conv = []
    for sql in sqls:
        call = {"type": "function", "function": {"name": "run_sql", "arguments": json.dumps({"sql_command": sql})}}
        conv += [{"role": "assistant", "content": "", "tool_calls": [call]},
                 {"role": "tool", "name": "run_sql", "content": str(rows(db, sql))}]
    return conv + [{"role": "assistant", "content": "Done."}]


def rmr(db: str, gold: str, *sqls: str) -> float:
    return result_match_reward([""], gold_rows=[rows(db, gold)], conversations=[conversation(db, *sqls)])[0]


class ScriptedEngine(RolloutEngine):
    """Returns fixed assistant turns (no model). `tokenizer` decides whether AgentTune folds tool turns."""

    def __init__(self, turns: list[str], tokenizer=None):
        self.turns, self.tokenizer, self.i = turns, tokenizer, 0

    def _get_tokenizer(self):
        return self.tokenizer

    def generate(self, prompts, tools, gen_cfg):
        out = self.turns[self.i] if self.i < len(self.turns) else ""
        self.i += 1
        return {"completions": [out], "logprobs": [None], "metadata": {}}


class ToolBlindTokenizer:
    """Stand-in for a chat template that ignores `tools` (Tiny Aya, Aya Expanse, North, Gemma 3)."""
    name_or_path = "tool-blind-template"

    def apply_chat_template(self, conversation, tools=None, tokenize=False, **_):
        text = "\n".join(f"{m['role']}: {m.get('content') or ''}" for m in conversation)
        return self.encode(text) if tokenize else text

    def encode(self, text, add_special_tokens=True):
        return [ord(c) % 256 for c in text]


def rollout_reward(db: str, gold: str, sql: str, tokenizer) -> tuple[float, list[str]]:
    def run_sql(sql_command: str) -> list:
        """Run a read-only SQLite query.

        Args:
            sql_command: The SQLite query to execute.
        """
        return rows(db, sql_command)

    turns = [json.dumps([{"tool_name": "run_sql", "parameters": {"sql_command": sql}}]), "Done."]
    fn = create_rollout_fn(rollout_engine=ScriptedEngine(turns, tokenizer), tools=[run_sql], max_steps=4,
                           reward_fn=result_match_reward)
    out = fn([{"prompt": "Who is older than 30?", "gold_rows": rows(db, gold)}])
    return out["rewards"][0], [m["role"] for m in out["conversations"][0]]


CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str) -> None:
    CHECKS.append((name, ok, detail))
    print(f"[{'OK ' if ok else 'FAIL'}] {name}: {detail}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tokenizer", default=None, help="optional local tokenizer path (e.g. Tiny Aya) for check (f)")
    args = ap.parse_args()
    db, db2 = make_db(), make_db(SECOND_DB_EXTRA)

    gold = "SELECT name, age FROM singer WHERE age > 30"
    r = rmr(db, gold, "SELECT age, name FROM singer WHERE age > 30")
    check("(a) column-order false reject", r == -1.0, f"same rows, columns swapped -> {r}")

    wrong = "SELECT name, age FROM singer WHERE age >= 30"
    r1, r2 = rmr(db, gold, wrong), rmr(db2, gold, wrong)
    check("(b) single-database false accept", r1 == 2.0 and r2 == -1.0,
          f"`age >= 30` for `age > 30`: {r1} on the given DB, {r2} on a second DB with an age-30 row")

    log = os.path.join(WORKDIR, "data", "scores.jsonl")
    n = sum(1 for _ in open(log)) if os.path.exists(log) else 0
    rec = json.loads(open(log).readline()) if n else {}
    check("(c) side-effect write to ./data/scores.jsonl", n == 3 and rec.get("name") == "sql.result_match_reward",
          f"{n} records appended to {os.path.relpath(log, WORKDIR)} under the working directory "
          f"(path from AGENTTUNE_SCORE_LOG at import, default data/scores.jsonl)")

    g = "SELECT name FROM singer ORDER BY age DESC"
    r = rmr(db, g, "SELECT name FROM singer ORDER BY age ASC")
    check("(d) row order ignored even when gold has ORDER BY", r == 2.0, f"reverse order accepted -> {r}")

    g = "SELECT name FROM singer WHERE country = 'Peru'"
    r = rmr(db, g, g, "SELECT nme FROM singer")
    check("(e) last tool result, not last successful query", r == -1.0,
          f"correct query followed by a failing exploratory query -> {r}")

    tok = ToolBlindTokenizer()
    if args.tokenizer:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(os.path.expanduser(args.tokenizer))
    plain, roles_plain = rollout_reward(db, gold, gold, tokenizer=None)
    folded, roles_folded = rollout_reward(db, gold, gold, tokenizer=tok)
    check("(f) tool-blind chat template: a correct rollout scores -1", plain == 2.0 and folded == -1.0 and "tool" not in roles_folded,
          f"gold query through create_rollout_fn: {plain} with tool turns {roles_plain}; {folded} once AgentTune "
          f"folds them into user turns for {getattr(tok, 'name_or_path', tok)} {roles_folded}")

    g = "SELECT fee + tax + bonus FROM singer WHERE id = 1"
    r = rmr(db, g, "SELECT bonus + tax + fee FROM singer WHERE id = 1")
    check("(g) exact float comparison", r == -1.0,
          f"0.1+0.2+0.3 vs 0.3+0.2+0.1 ({rows(db, g)} vs {rows(db, 'SELECT bonus + tax + fee FROM singer WHERE id = 1')}) -> {r}")

    r_dup = rmr(db, "SELECT country FROM singer", "SELECT DISTINCT country FROM singer")
    r_null = rmr(db, "SELECT name, country FROM singer WHERE id = 4", "SELECT name, country FROM singer WHERE age < 20")
    r_int = rmr(db, "SELECT COUNT(*) FROM singer", "SELECT COUNT(*) * 1.0 FROM singer")
    check("(h) handled correctly: duplicates, NULLs, 4 vs 4.0", (r_dup, r_null, r_int) == (-1.0, 2.0, 2.0),
          f"DISTINCT drops a duplicate -> {r_dup}; NULL == NULL -> {r_null}; 4 vs 4.0 -> {r_int}")

    print(f"\n{sum(ok for _, ok, _ in CHECKS)}/{len(CHECKS)} checks hold (workdir {WORKDIR})")
    raise SystemExit(0 if all(ok for _, ok, _ in CHECKS) else 1)


if __name__ == "__main__":
    main()
