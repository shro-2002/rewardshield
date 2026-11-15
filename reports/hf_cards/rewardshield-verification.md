---
license: cc-by-sa-4.0
tags: [text-to-sql, reward-verification, evaluation, lexsi-hackathon, rewardshield]
pretty_name: RewardShield verifier verdicts, labels and metrics
---
# RewardShield: verdicts, labels, metrics and logs

Per-sample verifier verdicts, oracle labels, LLM labels, analysis outputs and training/job logs for RewardShield.
Code, results and caveats: https://github.com/shro-2002/rewardshield

| Folder | Contents |
|---|---|
| `verdicts/` | accept/reject per sample for single-1, agenttune (shipped `result_match_reward` rule), random-4, targeted-4, random-16, with timings; test-suite oracle labels for the dev-A pool |
| `llm_labels/` | semantic-equivalence labels written by Claude (Anthropic) for 89 dev-A disagreement rows and 50 transfer-check rows; one LLM rater, not human-verified at release |
| `analysis/` | pre-registered bootstrap analyses (H1-H3, S1), E07 comparisons, verifier benchmark, AuditKIT agent metrics, reproducibility-check report |
| `exploratory/` | outputs of the independent audit scripts and the denominator reconciliation (post-hoc) |
| `logs/` | Kaggle job and training logs, training summaries |
| `configs/` | the exact GPU job commands |

Records are keyed by Spider question id (`qid`) and pool sample index; join them with the trajectories and splits
repositories of the same collection.

**Licence: CC BY-SA 4.0.** Our annotations, metrics and logs, released share-alike because label reasons quote short
fragments of Spider gold SQL and of model-generated SQL (see the trajectories repository for the terms of
generated text). Claude-written labels are disclosed as such.
