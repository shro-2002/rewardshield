# Upstream outcome (checked 2026-11-16)

**Result:** the AgentTune maintainers confirmed the bug and fixed it. [Lexsi-Labs/AgentTune#22](https://github.com/Lexsi-Labs/AgentTune/pull/22) merged on 2026-11-15 18:54 UTC (00:24 IST on Nov 16) and release **1.1.7** followed within a minute. Issue [#20](https://github.com/Lexsi-Labs/AgentTune/issues/20) and our PR [#21](https://github.com/Lexsi-Labs/AgentTune/pull/21) were closed with a point-by-point reply from the maintainer.

## What came from us, and what the maintainers changed

| Item | Outcome |
|---|---|
| Column-order false reject | Our commit was merged under our authorship. The maintainers added a pruning step so a 6-column result no longer tries all 720 column orders (about 1.2 s at 5,000 rows and 9 s at 20,000 per rollout in our version). Scores are unchanged. |
| Folded tool turns (every Tiny Aya rollout scored −1) | Confirmed, and wider than we reported: `structure_reward` was a constant −0.15 and `query_reward` saw no rows or errors on Tiny Aya, Aya Expanse, North and Gemma 3. The fix is in the rollout, which now gives the rewards the real `tool` turns. |
| **Our workaround for folded turns** | **Replaced, because it was forgeable.** Our patch read `Tool result for …:` text out of user turns. A tool call whose *name* contains a fake result line followed by a blank line made the reward return +2.0 without running any query. We reproduced this against our patch (reward function level; the rollout's echo of unknown tool names is the maintainer's observation). Our tests covered normal use only and missed it. **Do not use `result_match_reward.patch` in this directory; it is superseded.** |
| Last result vs last successful query | The last non-error result now counts. |
| Float comparison | Tolerance abs 1e-6 / rel 1e-9; ints exact. |
| Row order under `ORDER BY` | Optional `gold_sql` column; order counts when the gold query ends in a top-level `ORDER BY`. |
| `./data/scores.jsonl` write | Off by default; `AGENTTUNE_SCORE_LOG=path` turns it on. |
| Single-database false accepts | Optional `db_paths` column re-runs the query and `gold_sql` on extra read-only SQLite files; rows must match on each. |
| Found by the maintainers while checking | Queries that write their own rows (`select 'Joe', 31 union all …`) scored +2.0; dict or nested cells raised `TypeError`; echo-style tools could return the gold rows. All fixed. |

## Our check against the released package

We installed `agenttune==1.1.7` in a throwaway environment and re-ran our material:

- `reports/upstream/result_match_reward_repro.py` asserts the 1.1.5 behaviour, so it now reports **3/8** (it prints FAIL where the bug is gone): (a) column order → +2.0, (c) no log file written, (e) correct query then failing look-around → +2.0, (f) folded template through `create_rollout_fn` → +2.0, (g) float rounding → +2.0. Still true by design: (b) single-database false accept, (d) order ignored, until the new optional columns are supplied; (h) unchanged.
- With `db_paths` the `age >= 30` query is rejected (−1.0) and the correct query accepted (+2.0); with `gold_sql` a reversed `ORDER BY` result is rejected (−1.0).
- Our old forgery payload scores −1.0, and a literal-rows query (`select 'Joe', 31 union all …`) scores −1.0.
- Our own `RewardShieldReward` tests (`tests/test_agenttune_reward.py`) pass on 1.1.7 (6/6).

## What this means for the RewardShield results

All RewardShield experiments ran on AgentTune **1.1.5** (pinned in `pyproject.toml` and `uv.lock`) and are not rerun. The E03 "agenttune" column measures 1.1.5's comparison rule with the tool result given as a proper `tool` turn: 4.17% of correct samples rejected (column order), 4.31% false-accept share. Both figures describe 1.1.5; the column-order rejection is fixed in 1.1.7, and the single-database false accepts can now be reduced through `db_paths`.
