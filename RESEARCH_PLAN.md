# RewardShield: research plan

**Question.** How much verifier precision does a small SQL agent need? We compare single-database,
random multi-database and mutation-guided (targeted) test databases as the filter for training data,
on verifier error, verification cost and downstream accuracy of Tiny Aya Global.

**Track 3 (Agentic Fine-tuning)**, problem statements: data and database agents; reward design and
reward-hacking defences. Toolkits: AgentTune (rollouts, SFT, reward callables), AuditKIT (episode
import, scoring, paired significance).

## Prior work we build on (not claimed as ours)

| Work | What it established |
|---|---|
| Zhu et al. 2026, ReViSQL (arXiv 2603.20004 v4) | 32.8% of positive single-database rewards refuted by VeriEQL on Kimi-K2.6; VeriEQL verdict as a soft reward penalty |
| Zhong, Yu, Klein 2020 | Distilled test suites: per-gold-query mutants, greedy database selection; official Spider metric |
| Chen et al. 2025, ParSEval | Plan-aware test database generation for SQL equivalence evaluation |
| He et al. 2024, VeriEQL | Bounded SQL equivalence checking with counterexamples |
| XData (IIT Bombay) | Constraint-solved data to kill SQL mutants |
| ved-2004/RLVR-Text-to-SQL | Qwen2.5-Coder 1.5B/7B GRPO on Spider; single-DB vs test-suite gap roughly flat |
| AgentTune issue #11 / PR #12 | `where 1 = 1` exploit fixed with a text check and a single-database row match |

## What this project adds

A controlled small-model comparison: the same rollout pool scored by several verifiers against an
independent oracle, verification cost per unit of precision, and two (or more) fine-tuned arms
that differ only in which verifier filtered their training data.

## Phases

0. Feasibility: environment, model access, AgentTune rollout, AuditKIT import, GPU throughput.
1. Verifier library: isolated SQLite execution, random and targeted databases, mutants, greedy selection, tests.
2. Data: schema-disjoint Spider splits, official test-suite oracle, small synthetic finance check set, gold audit.
3. Training (priority order): base eval, gold SFT warm start, shared pool, static verifier comparison, single- and targeted-filtered SFT, held-out eval; then random arm, seeds, equal-budget control; then contamination dose-response, GRPO pilot.
4. Analysis per `HYPOTHESES.md`.
5. Package verifier with AgentTune integration and an upstream issue.
6. Round 1 submission per `SUBMISSION_CHECKLIST.md`.

**Floor deliverable** if training falls short: verifier audit + base-to-SFT results + one controlled comparison of the two filtered arms.
