"""RewardShieldReward through AgentTune's own scoring paths: create_rollout_fn and combine_rewards."""

import sqlite3
import warnings

import pytest
from agenttune.agentic.rewards.composite import combine_rewards
from agenttune.agentic.rollout_engines.rollout_factory import create_rollout_fn

from rewardshield.agent import make_run_sql, tool_call_text
from rewardshield.agenttune_reward import ReplayEngine, RewardShieldReward

# No singer is exactly 30 on the original database, so `age >= 30` coincides with gold there.
SCHEMA = """
CREATE TABLE singer (id INTEGER PRIMARY KEY, name TEXT, age INTEGER, country TEXT);
INSERT INTO singer VALUES (1,'Ana',25,'Peru'),(2,'Bo',41,'Chile'),(3,'Cy',35,'France'),(4,'Di',19,'Peru');
"""
GOLD = "SELECT name, age FROM singer WHERE age > 30"
CORRECT, REORDERED, WRONG = GOLD, "SELECT age, name FROM singer WHERE age > 30", "SELECT name, age FROM singer WHERE age >= 30"


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "orig.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return str(path)


def _rollout(db, reward, preds):
    episodes = [[{"role": "assistant", "content": tool_call_text(p)}, {"role": "assistant", "content": "Done."}]
                for p in preds]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rollout_fn = create_rollout_fn(rollout_engine=ReplayEngine(episodes), tools=[make_run_sql(db)],
                                       max_steps=4, reward_fn=reward)
        return rollout_fn([{"prompt": "Who is older than 30?", "gold_sql": GOLD, "db_path": db, "qid": "q1"}
                           for _ in preds])


def test_targeted_accepts_correct_and_reordered_rejects_wrong(db, tmp_path):
    out = _rollout(db, RewardShieldReward("targeted", 4, cache_dir=str(tmp_path / "suites")), [CORRECT, REORDERED, WRONG])
    assert out["rewards"] == [2.0, 2.0, -1.0]
    assert [t.reward for t in out["trajectories"]] == [2.0, 2.0, -1.0]
    assert out["tool_call_counts"] == [1, 1, 1]


def test_single_database_accepts_the_wrong_query(db):
    out = _rollout(db, RewardShieldReward("single"), [CORRECT, REORDERED, WRONG])
    assert out["rewards"] == [2.0, 2.0, 2.0]


def test_grpo_path_combine_rewards_scores_rollout_conversations(db, tmp_path):
    reward = RewardShieldReward("targeted", 4, cache_dir=str(tmp_path / "suites"))
    out = _rollout(db, reward, [CORRECT, REORDERED, WRONG])
    n = len(out["conversations"])
    combined = combine_rewards([reward])  # what TrlAgenticGrpo hands to TRL's GRPOTrainer
    scores = combined(completions=out["responses"], conversations=out["conversations"],
                      gold_sql=[GOLD] * n, db_path=[db] * n, qid=["q1"] * n)
    assert scores == [2.0, 2.0, -1.0]


def test_missing_gold_scores_zero_and_writes_no_score_log(db, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reward = RewardShieldReward("single")
    assert reward([[{"role": "assistant", "content": "hi"}]]) == [0.0]
    out = _rollout(db, reward, [CORRECT])
    assert out["rewards"] == [2.0]
    assert not (tmp_path / "data" / "scores.jsonl").exists()


def test_no_executed_sql_is_rejected(db):
    reward = RewardShieldReward("single")
    assert reward([[{"role": "assistant", "content": "I don't know."}]], gold_sql=[GOLD], db_path=[db]) == [-1.0]


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        RewardShieldReward("mutant")
