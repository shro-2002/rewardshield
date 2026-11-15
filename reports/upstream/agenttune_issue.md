# DRAFT (not filed): `result_match_reward` rejects correct queries (column order, folded tool turns) and accepts wrong ones a second database would catch

**Version:** agenttune 1.1.5 (PyPI). `src/agenttune/agentic/rewards/builtin_rewards/sql.py` and `src/agenttune/utils/score_logger.py` are byte-identical on `main` (2aecde4, 2026-11-14) and in 1.1.6 (the 1.1.5...1.1.6 tag compare touches only `.github/dependabot.yml` and `SECURITY.md`).

**Related:** #11 proposed `result_match_reward`; it shipped in #12 (merged 2026-11-10). None of the points below is addressed there or in any later commit, and no open or closed issue mentions them (searched `result_match_reward`, `scores.jsonl`).

## What happens

`result_match_reward` compares the last `"tool"` turn's rows with `gold_rows` as an order-blind multiset. Verified by the repro below:

| # | Case | Reward | Expected |
|---|---|---|---|
| a | Correct rows, columns in another order (`select age, name` for `select name, age`) | −1.0 | +2.0 |
| b | Wrong query that coincides with gold on the one database (`age >= 30` for `age > 30`, no row with age 30) | +2.0 (−1.0 once a second database has an age-30 row) | −1.0 |
| c | Every call appends a record to `./data/scores.jsonl` under the current working directory | – | opt-in, or documented |
| d | Gold has a top-level `ORDER BY`, prediction returns the reverse order | +2.0 | arguable; Spider-style evaluation compares order when gold orders |
| e | Correct query, then a failing exploratory query | −1.0 (the error dict is the last tool result) | design choice; worth documenting |
| f | Correct query in a rollout whose chat template ignores `tools` (Tiny Aya; also a stand-in template) | −1.0 | +2.0 |
| g | `fee + tax + bonus` vs `bonus + tax + fee` (0.6000000000000001 vs 0.6) | −1.0 | +2.0 |
| h | Duplicates (`DISTINCT` drops a row), `NULL == NULL`, `4` vs `4.0` | −1.0, +2.0, +2.0 | correct as is |

(f) matters most for small models: for a template that ignores `tools`, `_execute_trajectory` folds every tool result into a user turn (`fold_tool_messages_into_user`), and `metadata["conversation"]`, `conversations` and the completions the reward sees are the folded ones. No `"tool"` turn is left, so the reward returns −1.0 ("no tool result") for every rollout, correct or not. The repro shows this through `create_rollout_fn` with the real Tiny Aya tokenizer (`--tokenizer`) and with a stand-in tokenizer.

## Measured impact (RewardShield, Lexsi hackathon project)

On 1,360 Tiny Aya Global 3B samples on Spider dev (dev-A, 719 correct by a test-suite oracle), with `result_match_reward` fed AgentTune-format `"tool"` turns on the original database:

- It rejects **4.17%** of oracle-correct samples. An execution-match verifier on the same single database that ignores column order rejects 0.00%.
- Its false-accept share (wrong accepts / accepts) is **4.31%**, against **3.88%** for that single-database verifier and **1.39%** for a 4-database verifier (original database plus 3 generated ones chosen to separate gold from its mutants; 2.08% when averaged over 200 random draws of its fill databases).
- In a blind-labelled set of 35 equivalent-to-gold samples where some verifier disagreed with the oracle, 29 differ from gold only in column order; this reward rejects all of them.

These numbers are for the unfolded shape. Inside an actual Tiny Aya rollout, point (f) makes every reward −1.0.

## Repro

```bash
pip install agenttune==1.1.5
python reports/upstream/result_match_reward_repro.py                                  # stand-in tool-blind template
python reports/upstream/result_match_reward_repro.py --tokenizer ~/models/tiny-aya-global   # real Tiny Aya tokenizer, no weights
```

Self-contained (stdlib `sqlite3`, temp databases, temp working directory). Each row of the table is an assertion; the script exits non-zero if one fails. Output on 1.1.5: `8/8 checks hold`.

## Proposed fix (patch attached: `result_match_reward.patch`)

1. **Column order.** Accept when one column permutation, applied to every row, makes the multisets equal (2 to 6 columns of equal width). A per-row sort would be wrong: it would accept `[(a,b),(a,b)]` for `[(a,b),(b,a)]`; the patch does not.
2. **Folded tool results.** Also read user turns written in the rollout's default `tool_result_format` (`Tool result for {name}: {content}\nUse this result ...`), splitting turns where consecutive results were merged.
3. Backward compatible otherwise: same scores (+2 / −1 / 0), same signature, same logging.

Test (`tests/test_result_match_reward_patch.py`, applies the patch to a copy of the installed file): column-reordered correct rows +2.0 (shipped: −1.0); wrong rows with swapped columns, a missing row, and the per-row-sort trap stay −1.0; folded correct result +2.0 (shipped: −1.0), folded wrong result −1.0.

## Not fixed by the patch (recommendations)

- **Single database (b).** A reward that compares rows on one database pays any query that coincides with gold there. Comparing on a few extra databases (generated from the schema, or the gold query's mutants) closes most of this; a hook for extra databases or a pluggable comparator would let users add it.
- **Score log side effect (c).** `log_score` writes `./data/scores.jsonl` for every built-in reward by default, relative to the working directory at call time; inside a training loop that grows without bound and lands wherever the job was started. Suggest off by default (or only when `AGENTTUNE_SCORE_LOG` is set), and documenting it in the reward docstrings.
- **Order (d) and floats (g).** Compare row order when gold has a top-level `ORDER BY`; compare floats after rounding (e.g. 6 digits).
- **Last vs last successful (e).** Document it, or score the last tool result that is not an error.
