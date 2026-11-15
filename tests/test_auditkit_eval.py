"""scripts/auditkit_eval.py on a two-episode fixture: AuditKIT conversion, metric definitions, timing labels."""

import importlib.util
import json
import sqlite3
from pathlib import Path

import pytest

from rewardshield.agent import TOOL_RESULT_FORMAT, tool_call_text

spec = importlib.util.spec_from_file_location("auditkit_eval", Path(__file__).resolve().parents[1] / "scripts" / "auditkit_eval.py")
ae = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ae)

GOLD = "SELECT name FROM singer WHERE age > 30"


def _call(sql):
    return {"role": "assistant", "content": tool_call_text(sql),
            "tool_calls": [{"type": "function", "function": {"name": "run_sql", "arguments": json.dumps({"sql_command": sql})}}]}


def _result(content):
    return {"role": "user", "content": TOOL_RESULT_FORMAT.format(name="run_sql", content=content)}


@pytest.fixture()
def fixture(tmp_path):
    db = tmp_path / "s.sqlite"
    with sqlite3.connect(db) as conn:
        conn.executescript("CREATE TABLE singer (id INTEGER PRIMARY KEY, name TEXT, age INTEGER);"
                           "INSERT INTO singer VALUES (1,'Ana',25),(2,'Bo',41);")
    questions = {q: {"qid": q, "question": "Who is over 30?", "gold": GOLD, "db_path": str(db)} for q in ("q1", "q2")}
    sys_msg = {"role": "system", "content": "schema"}
    records = [
        {"qid": "q1", "sample": 0, "final_sql": GOLD, "messages": [sys_msg, {"role": "user", "content": "Q"},
                                                                     _call(GOLD), _result([["Bo"]]),
                                                                     {"role": "assistant", "content": "Bo."}]},
        {"qid": "q2", "sample": 0, "final_sql": None, "messages": [sys_msg, {"role": "user", "content": "Q"},
                                                                     _call("SELECT nme FROM singer"),
                                                                     _result([{"error": "no such column: nme"}]),
                                                                     {"role": "assistant", "content": '[{"tool_name": "run_sql", oops'}]},
    ]
    path = tmp_path / "M_devB.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records))
    (tmp_path / "M_devB_oracle.jsonl").write_text(
        "\n".join(json.dumps({"qid": q, "sample": 0, "oracle": q == "q1"}) for q in ("q1", "q2")))
    log = tmp_path / "v.log"
    log.write_text('Loading...\n{"rollouts": 2, "seconds": 5.0, "rollouts_per_min": 24.0}\n')
    lat = tmp_path / "lat_M.jsonl"
    lat.write_text('{"qid": "q1", "sample": 0, "seconds": 1.5}\n{"qid": "q2", "sample": 0, "seconds": 2.5}\n')
    return {"path": str(path), "questions": questions, "log": str(log), "lat": str(lat), "records": records, "tmp": tmp_path}


def test_unfold_pairs_tool_results_to_calls(fixture):
    msgs = ae.unfold(fixture["records"][0]["messages"])
    assert [m["role"] for m in msgs] == ["user", "assistant", "tool", "assistant"]
    assert msgs[2]["tool_call_id"] == msgs[1]["tool_calls"][0]["id"] and msgs[2]["content"] == "[['Bo']]"


def test_execution_stats_definitions(fixture):
    ex = ae.execution_stats(fixture["records"])
    assert ex["parsed_calls"] == 2 and ex["executed_ok_calls"] == 1 and ex["call_execution_rate"] == 0.5
    assert ex["episode_all_parsed_rate"] == 0.5  # q2 has an unparsed call attempt
    assert ex["episode_clean_rate"] == 0.5


def test_evaluate_end_to_end(fixture):
    rep = ae.evaluate({"M": fixture["path"]}, fixture["questions"], {"M": fixture["log"]}, {}, str(fixture["tmp"] / "c"))
    m = rep["models"]["M"]
    assert (m["success"], m["decided"], m["task_success_rate"]) == (1, 2, 0.5)
    assert m["tool_call_validity_eligible"] == 2 and m["tool_call_validity_mean"] == 1.0
    assert m["episode_time"]["batch16_throughput"]["seconds_per_episode"] == 2.5
    assert m["episode_time"]["batch1_latency"] is None  # missing stays missing
    assert m["targeted4_vs_oracle"] == {"accepts_oracle_wrong": 0, "rejects_oracle_correct": 0}
    assert set(m["verifier_cpu_ms_per_episode"]) == {"single-1", "targeted-4"}
    ae.write_markdown(rep, str(fixture["tmp"] / "out.md"))
    assert "missing" in (fixture["tmp"] / "out.md").read_text()


def test_batch1_latency_only_from_file(fixture):
    rep = ae.evaluate({"M": fixture["path"]}, fixture["questions"], {}, {"M": fixture["lat"]}, str(fixture["tmp"] / "c"))
    et = rep["models"]["M"]["episode_time"]
    assert et["batch16_throughput"] is None and et["batch1_latency"]["mean_s"] == 2.0
