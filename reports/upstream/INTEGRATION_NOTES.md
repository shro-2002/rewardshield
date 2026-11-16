> **Update 2026-11-16:** the upstream issue and patch described here were resolved in AgentTune 1.1.7 ([#22](https://github.com/Lexsi-Labs/AgentTune/pull/22), merged). Our workaround for folded tool turns was replaced because it was forgeable; see [OUTCOME.md](OUTCOME.md). The integration below was built and measured on 1.1.5 and its tests also pass on 1.1.7.

# Toolkit integration notes (Track 3): AgentTune and AuditKIT in RewardShield

Pinned: `agenttune==1.1.5`, `auditkit[jsonschema]==1.1.11` (pyproject.toml, uv.lock). Newer releases exist (checked 2026-11-15) and were not adopted:

- **agenttune 1.1.6.** The GitHub compare 1.1.5...1.1.6 changes only `.github/dependabot.yml` and `SECURITY.md`, and `main` equals 1.1.6. The reward, rollout and score-logger code we use is the same.
- **auditkit 1.1.12.** `agent_eval` gains `AgentEvalSpec(score_partial_on_error=...)` (default off; scores a state or artifact oracle on errored runs). A dict attached to `episode.final_state` is now reported as `observed`. The summary adds a "scored on observed evidence" count. None of these touches our use: no errored runs, and a `CustomPredicate` oracle.

## What is used, and where

### AgentTune

| Piece | Module | Used in |
|---|---|---|
| Reward contract `f(completions, **kwargs) -> list[float]` | `agenttune.agentic.rewards.composite.combine_rewards` (GRPO path) and `agenttune.agentic.rollout_engines.rollout_factory.create_rollout_fn(reward_fn=...)` → `_wrap_reward_fn` (rollout path) | `src/rewardshield/agenttune_reward.py` (`RewardShieldReward`) |
| Rollout loop: tool-call parsing, tool execution, reward scoring, `Trajectory.reward` | `create_rollout_fn`, `_execute_trajectory` | `ReplayEngine` + `scripts/demo_agenttune_reward.py`, `tests/test_agenttune_reward.py` |
| Engine interface | `agenttune.agentic.rollout_engines.base.RolloutEngine` | `ReplayEngine` (replays recorded assistant turns, same pattern as AgentTune's `DemoRolloutEngine`) |
| Tool-call parser, tool fallback prompt, tool-result format | `tool_call_parse.extract_tool_calls_from_text`, `DEFAULT_TOOLS_FALLBACK_PROMPT`, `DEFAULT_TOOL_RESULT_FORMAT` | `src/rewardshield/rollout.py`, `agent.py` (batched rollouts in AgentTune's format; existing) |
| Baseline reward | `builtin_rewards.sql.result_match_reward` | `scripts/score_samples.py` (E03 "agenttune" column; existing), `reports/upstream/` |
| Optional score log | `agenttune.utils.score_logger.ScoreLogger` | `RewardShieldReward(score_log=path)`; off by default |

`RewardShieldReward(mode="targeted", k=4)` is the default; `"single"` and `"random", k` are options. It reads dataset columns `gold_sql`, `db_path`, `qid` (optional), and reads the trajectory from `conversations[i]` when present, else from the completion. Suites are cached per question. `single` writes nothing. `random`/`targeted` generate candidate databases in `cache_dir` (a fresh temp dir by default). Scores follow `result_match_reward`: +2 accept, −1 reject, 0 for no usable gold.

### AuditKIT

| Piece | Module | Used in |
|---|---|---|
| Trajectory schema + importer | `auditkit.agent_eval.episode_from_openai_messages`, `AgentEpisode`, `AgentCase` | `scripts/auditkit_eval.py` (recorded Tiny Aya turns are first un-folded: "Tool result for run_sql: …" user turns become `tool` turns paired by call id) |
| Outcome oracle | `auditkit.agent_eval.CustomPredicate` (version `test-suite-oracle-labels-v1`) | task success = the existing test-suite oracle label, not recomputed |
| Runner, recorded mode | `AgentEvalSpec(mode="recorded")`, `AgentEvalRunner().run` | per model |
| Metrics | `tool_call_validity`, `redundant_tool_calls`, `agent_loop_detection` (`auditkit.metrics.agent`) | `reports/toolkit_metrics.{json,md}` |
| Source-vs-oracle disagreement (AG-05) | episode `source_verdict` = targeted-4 verdict | counts of targeted-4 accepts of oracle-wrong / rejects of oracle-correct episodes |
| Run summary | `AgentEvalResult.summary()` | quoted per model in `toolkit_metrics.md` |

The only earlier AuditKIT use was one importer call in `scripts/smoke_phase0.py`.

## What is not used (and is not claimed)

- **Training.** Training was raw TRL `SFTTrainer` LoRA on verifier-filtered samples (reward-filtered SFT). It did not use AgentTune's trainers (`TrlAgenticGrpo`, the SFT backends) and it was not RL. The GRPO path is shown only as far as the `combine_rewards` callable that `TrlAgenticGrpo` would hand to TRL's `GRPOTrainer`, called on rollout output (`tests/test_agenttune_reward.py::test_grpo_path_combine_rewards_scores_rollout_conversations`). No `GRPOTrainer` was run.
- **AgentTune.** Its eval and agent_eval modules, the DECIDE/self-heal spine, the vLLM/API engines, and its own SQL tool (`SQLDatabaseTool`). We use our sandboxed `run_sql`.
- **AuditKIT.** Not used: the LLM judges (`task_completion`, `tool_selection`), deployed and harness modes, repeated-trial reliability, and reference-based tool metrics (`tool_call_f1`, `trajectory_match`; gold trajectories exist but were not wired in as references). Also unused: sidecars, the CLI, and the AgentTune file importer (`episodes_from_agenttune`). Our recorded files are not in an AgentTune export format.

## How the pieces connect

```
data/splits/devB.jsonl (gold, db_path)
        │
recorded episodes runs/E04/out/E0x_devB.jsonl ──► ReplayEngine ──► agenttune create_rollout_fn (parse calls, run run_sql)
        │                                                                 │ reward_fn
        │                                                                 ▼
        │                                         RewardShieldReward (rewardshield.verifiers: single / random-k / targeted-k)
        │
        ├──► unfold ──► auditkit episode_from_openai_messages ──► AgentEvalRunner (recorded)
        │                       ▲ case outcome: oracle label (E0x_devB_oracle.jsonl)   ▲ source_verdict: targeted-4
        └──► v*.log throughput, lat_*.jsonl (when present), CPU timing of verify() ──► reports/toolkit_metrics.{json,md}
```

## Reproduce (CPU only, no model weights)

```bash
.venv/bin/python -m pytest -q                                           # full suite
.venv/bin/python scripts/demo_agenttune_reward.py --limit 0             # all 379 E05 dev-B episodes through AgentTune's rollout loop
.venv/bin/python scripts/auditkit_eval.py                               # writes reports/toolkit_metrics.{json,md}
# when the Kaggle job lands (oracle file must sit next to it as E07_devB_oracle.jsonl):
.venv/bin/python scripts/auditkit_eval.py --model E07=runs/E07/out/E07_devB.jsonl \
    --latency E00=…/lat_E00.jsonl --latency E05=…/lat_E05.jsonl --latency E07=…/lat_E07.jsonl
.venv/bin/python reports/upstream/result_match_reward_repro.py [--tokenizer ~/models/tiny-aya-global]
```

Demo output on E05 dev-B (379 episodes): replay fidelity 379/379 (the final SQL from AgentTune's replay equals the recorded one). Single-1 accepts 266, 31 of them oracle-wrong, and rejects 0 oracle-correct. Targeted-4 accepts 252, 18 oracle-wrong, and rejects 1 oracle-correct. Run time 1.0 s and 21.1 s including suite builds.

## Limitations

- **Replay, not generation.** `ReplayEngine` feeds recorded turns, so this checks the reward and the rollout plumbing, not a live policy. It assumes AgentTune's synchronous rollout order (`async_rollouts=False`, the default). It has no tokenizer, so AgentTune keeps `tool` turns unfolded. `RewardShieldReward` reads folded turns too (via `final_sql`), and the recorded files are folded, so both shapes are covered.
- **tool_call_validity is uninformative here.** It is 100% for every model: one tool with one string argument, and unparseable calls never become calls. The execution-based rates carry the signal. "Unparsed call attempt" is a text heuristic (`tool_name`/`sql_command` in an assistant turn without parsed calls). On dev-B each such episode also made no parsed call.
- **Timings.** Batch-16 seconds/episode are amortised throughput from the Kaggle T4 logs as recorded, not latency. Batch-1 latency is `missing` until `lat_*.jsonl` exist; nothing is imputed. Verifier times are one laptop CPU (arm64 macOS) run and vary by about ±20% between runs. Suite build time (median about 0.04 s/question) is reported separately.
- **Task success uses the existing oracle labels.** The oracle's suites are smaller than the official test suite, so false-accept counts are lower bounds (RESULTS.md E03). The targeted-4 vs oracle counts are on greedy evaluation episodes, not the E03 pool.
- **The E03 "agenttune" baseline** fed `result_match_reward` unfolded `tool` turns. In a real AgentTune rollout with Tiny Aya's template, the reward would see folded turns and return −1.0 for every rollout (`result_match_reward_repro.py` check f). E03 measures its comparison rule, not its in-rollout behaviour.
- **Dev-B suites are built in temp dirs.** Nothing is written to `data/cache/suites`.
