"""RewardShield verifiers as an AgentTune reward function, plus a replay engine for recorded runs.

AgentTune 1.1.5 consumes rewards as batch callables ``f(completions, **kwargs) -> list[float]``:
- ``combine_rewards`` (agenttune.agentic.rewards.composite) wraps them for TRL's GRPOTrainer, which
  passes dataset columns and rollout fields such as ``conversations`` as keyword arguments;
- ``create_rollout_fn(..., reward_fn=...)`` scores each rollout through ``_wrap_reward_fn``, calling
  ``reward_fn(completions, prompts=..., **dataset_columns)`` and storing the score in ``Trajectory.reward``.
``RewardShieldReward`` follows that contract. Per example it needs the dataset columns ``gold_sql`` and
``db_path`` (``qid`` optional). The scored answer is the last SQL whose tool result was not an error
(rewardshield.agent.final_sql), read from ``conversations[i]`` when given, else from the completion.
Unlike AgentTune's ``result_match_reward`` it re-executes the query (column order ignored, row order
kept only when gold has a top-level ORDER BY) on k databases, and writes no score log by default.

``ReplayEngine`` is an AgentTune ``RolloutEngine`` that replays recorded assistant turns instead of
sampling a model, so recorded trajectories go through AgentTune's real rollout loop (tool parsing,
tool execution, reward scoring) on CPU, as AgentTune's own ``DemoRolloutEngine`` does for tests.
"""

from __future__ import annotations

import hashlib
import tempfile
from typing import Any

from agenttune.agentic.rollout_engines.base import RolloutEngine

from .agent import final_sql
from .sqlexec import execute, has_top_level_order
from .verifiers import QuestionSuite, Verdict, build_suite, verify

MODES = ("single", "random", "targeted")


class RewardShieldReward:
    """AgentTune reward: ``accept`` if the agent's final SQL matches gold on every selected database.

    mode/k: ``targeted`` 4 (default), ``random`` k, or ``single`` (original database only).
    Scores default to result_match_reward's scale (+2 / -1, 0 when an example has no usable gold),
    so it can replace that reward in an existing ``reward_funcs`` list.
    cache_dir: where candidate databases are generated (a fresh temp dir if None; ``single`` writes nothing).
    score_log: optional JSONL path for AgentTune's ScoreLogger; None (default) writes no log.
    """

    def __init__(self, mode: str = "targeted", k: int = 4, *, cache_dir: str | None = None,
                 accept: float = 2.0, reject: float = -1.0, missing: float = 0.0,
                 score_log: str | None = None) -> None:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
        self.mode, self.k = mode, 1 if mode == "single" else k
        self.cache_dir = cache_dir
        self.accept, self.reject, self.missing = accept, reject, missing
        self.__name__ = f"rewardshield_{mode}_{self.k}"  # combine_rewards logs functions by name
        self._suites: dict[str, QuestionSuite] = {}
        self._schema_cache: dict = {}
        self._logger = None
        if score_log:
            from agenttune.utils.score_logger import ScoreLogger
            self._logger = ScoreLogger(output_file=score_log)
        self.last_verdicts: list[Verdict | None] = []

    def __call__(self, completions: list[Any], **kwargs: Any) -> list[float]:
        golds, dbs = kwargs.get("gold_sql"), kwargs.get("db_path")
        qids, convs = kwargs.get("qid"), kwargs.get("conversations")
        scores, self.last_verdicts = [], []
        for i, completion in enumerate(completions):
            gold, db = _at(golds, i), _at(dbs, i)
            turns = _at(convs, i) if isinstance(_at(convs, i), list) else completion
            pred = final_sql(turns) if isinstance(turns, list) else None
            verdict = None
            if not (gold and db):
                score, reason = self.missing, "no gold_sql/db_path for this example"
            elif not pred:
                score, reason = self.reject, "no executed SQL in the trajectory"
            else:
                verdict = verify(self._suite(_at(qids, i) or _key(db, gold), gold, db), pred, self.mode, self.k)
                if verdict.n_exec == 0:
                    score, reason = self.missing, verdict.reason
                else:
                    score, reason = (self.accept if verdict.accept else self.reject), verdict.reason
            self.last_verdicts.append(verdict)
            if self._logger:
                self._logger.log(self.__name__, score, reasons=[reason], meta={"index": i})
            scores.append(score)
        return scores

    def _suite(self, qid: str, gold: str, db: str) -> QuestionSuite:
        if qid not in self._suites:
            if self.mode == "single":  # needs only the original database: no candidates, no writes
                self._suites[qid] = QuestionSuite(qid, gold, db, [], {db: execute(db, gold)}, has_top_level_order(gold))
            else:
                if self.cache_dir is None:
                    self.cache_dir = tempfile.mkdtemp(prefix="rewardshield-suites-")
                self._suites[qid] = build_suite(qid, gold, db, self.cache_dir, schema_cache=self._schema_cache)
        return self._suites[qid]


def _at(column: Any, i: int) -> Any:
    return column[i] if isinstance(column, (list, tuple)) and i < len(column) else None


def _key(db: str, gold: str) -> str:
    return "q" + hashlib.sha256(f"{db}|{gold}".encode()).hexdigest()[:12]


class ReplayEngine(RolloutEngine):
    """Replays recorded assistant turns, one recorded episode per AgentTune trajectory, in order.

    A generate call whose conversation has no assistant turn starts the next episode; later calls
    return that episode's next assistant turn ("" once it runs out, which ends AgentTune's loop).
    No tokenizer, so AgentTune keeps tool results as "tool" turns (it folds them into user turns only
    for a tokenizer whose chat template ignores tools).
    """

    def __init__(self, episodes: list[list[dict]]) -> None:
        self._turns = [[m.get("content") or "" for m in msgs if m.get("role") == "assistant"] for msgs in episodes]
        self._episode = -1

    def _get_tokenizer(self) -> None:
        return None

    def generate(self, prompts: list[dict], tools: list[Any], gen_cfg: dict[str, Any]) -> dict[str, Any]:
        done = sum(1 for m in prompts if isinstance(m, dict) and m.get("role") == "assistant")
        if done == 0:
            self._episode += 1
        turns = self._turns[self._episode]
        return {"completions": [turns[done] if done < len(turns) else ""], "logprobs": [None],
                "metadata": {"backend": "replay"}}
