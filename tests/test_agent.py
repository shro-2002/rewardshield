import json
import sqlite3

import pytest

from rewardshield.agent import TOOL_RESULT_FORMAT, final_sql, full_system_prompt, gold_trajectory, make_run_sql


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "d.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript("CREATE TABLE t (id INTEGER PRIMARY KEY, x TEXT); INSERT INTO t VALUES (1,'a'),(2,'b');")
    return str(path)


def _call(sql):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"type": "function", "function": {"name": "run_sql", "arguments": json.dumps({"sql_command": sql})}}]}


def test_tool_result_format_matches_agenttune():
    from agenttune.agentic.rollout_engines.rollout_factory import DEFAULT_TOOL_RESULT_FORMAT
    assert TOOL_RESULT_FORMAT == DEFAULT_TOOL_RESULT_FORMAT


def test_final_sql_is_last_successful_call():
    conv = [{"role": "user", "content": "q"},
            _call("SELECT x FROM t"), {"role": "user", "content": "Tool result for run_sql: [['a'], ['b']]"},
            _call("SELECT nope FROM t"), {"role": "user", "content": "Tool result for run_sql: [{'error': 'no such column'}]"},
            {"role": "assistant", "content": "done"}]
    assert final_sql(conv) == "SELECT x FROM t"
    assert final_sql([{"role": "assistant", "content": "no tools"}]) is None


def test_run_sql_is_sandboxed(db):
    run_sql = make_run_sql(db)
    assert run_sql("SELECT x FROM t ORDER BY id") == [["a"], ["b"]]
    assert "error" in run_sql("DELETE FROM t")[0]


def test_gold_trajectory_uses_agenttune_fallback(db):
    traj = gold_trajectory("How many rows?", "SELECT COUNT(*) FROM t", db)
    assert "To call tools, reply with only a JSON list" in traj[0]["content"]
    assert json.loads(traj[2]["content"])[0]["parameters"]["sql_command"] == "SELECT COUNT(*) FROM t"
    assert traj[3]["content"].startswith("Tool result for run_sql: [[2]]")
    assert full_system_prompt(db).count("run_sql") >= 2
