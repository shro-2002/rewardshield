"""reports/upstream/result_match_reward.patch applied to a copy of the installed AgentTune sql.py."""

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from agenttune.agentic.rewards.builtin_rewards import sql as installed
from agenttune.agentic.rollout_engines.rollout_factory import fold_tool_messages_into_user

PATCH = Path(__file__).resolve().parents[1] / "reports" / "upstream" / "result_match_reward.patch"
REL = Path("src/agenttune/agentic/rewards/builtin_rewards/sql.py")
GOLD = [("Bo", 41), ("Cy", 35)]


@pytest.fixture()
def patched(tmp_path, monkeypatch):
    target = tmp_path / REL
    target.parent.mkdir(parents=True)
    shutil.copy(installed.__file__, target)
    subprocess.run(["patch", "-p1", "-d", str(tmp_path), "-i", str(PATCH)], check=True, capture_output=True)
    spec = importlib.util.spec_from_file_location("sql_patched", target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "log_score", lambda *a, **k: None)
    monkeypatch.setattr(installed, "log_score", lambda *a, **k: None)
    return mod


def _conv(rows):
    call = {"type": "function", "function": {"name": "run_sql", "arguments": json.dumps({"sql_command": "q"})}}
    return [{"role": "assistant", "content": "", "tool_calls": [call]},
            {"role": "tool", "name": "run_sql", "content": str(rows)},
            {"role": "assistant", "content": "Done."}]


def _score(mod, rows, gold=GOLD, fold=False):
    conv = fold_tool_messages_into_user(_conv(rows)) if fold else _conv(rows)
    return mod.result_match_reward([""], gold_rows=[gold], conversations=[conv])[0]


def test_column_order_no_longer_rejected(patched):
    reordered = [(41, "Bo"), (35, "Cy")]
    assert _score(installed, reordered) == -1.0  # the shipped behaviour
    assert _score(patched, reordered) == 2.0
    assert _score(patched, GOLD) == 2.0


def test_wrong_rows_still_rejected(patched):
    assert _score(patched, [(25, "Ana"), (19, "Di")]) == -1.0  # `age < 30`, columns swapped
    assert _score(patched, [("Bo", 41)]) == -1.0  # missing a row


def test_permutation_is_one_per_result_not_per_row(patched):
    gold = [("a", "b"), ("b", "a")]
    assert _score(patched, [("a", "b"), ("a", "b")], gold=gold) == -1.0


def test_folded_tool_result_is_read(patched):
    assert _score(installed, GOLD, fold=True) == -1.0  # no "tool" turn left after folding
    assert _score(patched, GOLD, fold=True) == 2.0
    assert _score(patched, [("Ana", 25)], fold=True) == -1.0
