# Pre-registered hypotheses and analysis plan

Status: **draft v1, written 2026-11-14 before any model sampling.** Sample sizes marked *TBD-P0* are
fixed from measured Phase 0 throughput and recorded in `DECISIONS.md` with a timestamp before the
shared rollout pool is drawn. After the pool is drawn this file is frozen; later changes go in an
appended "Deviations" section with reasons, and the original text stays.

## Terms

- **Sample**: one final SQL query produced by one rollout for one question.
- **Verifier V**: returns accept or reject for (gold SQL, predicted SQL, schema).
  - `single`: execution match on the original Spider database (row multiset, column order ignored; order compared only when the gold has a top-level ORDER BY).
  - `random-k`: match on the original database plus k-1 random schema-preserving databases.
  - `targeted-k`: match on the original database plus k-1 databases chosen to kill mutants of the gold query.
  - `agenttune`: AgentTune's patched `result_match_reward` (single-database row match), reported as the shipped baseline.
- **Oracle O**: accept iff the predicted query matches the gold on every database of the official Spider test suite (Zhong et al. 2020) for that db_id. Built by others, on dev databases our verifiers never see. Finite agreement, not a proof of equivalence. Second check: 100 hand-labelled disagreements.
- **False-accept share** = |V accepts and O rejects| / |V accepts|.
- **False-accept mass** = |V accepts and O rejects| / |all samples|.
- **False-reject rate** = |V rejects and O accepts| / |O accepts|.
- **Acceptance coverage** = |V accepts| / |all samples|.
- **Held-out test-suite accuracy** = share of held-out questions whose greedy final SQL is accepted by O.
- **Execution accuracy** = same, with the single original database only.
- **Verification cost** = median and p95 ms per sample, SQL executions per sample, and one-off construction seconds per gold query (amortised cost = construction / samples per query + per-sample cost).

## Splits (schema-disjoint)

- **train**: Spider train databases. Warm-start SFT data and the training rollout pool. No oracle exists here.
- **dev-A**: half of the 20 Spider dev databases (fixed seeded split by db_id). The **audit pool** is drawn here with the same warm-start policy and sampling settings as the training pool; it is labelled by the oracle and never used for training. Verifier design choices (k, mutant operators) may be tuned only on dev-A.
- **dev-B**: the other half. Final held-out model evaluation only, touched once per arm.

## Primary hypotheses

- **H1** Targeted-4 has a lower false-accept share than single on the dev-A audit pool.
- **H2** Targeted-4 has a lower false-accept share than random-4 on the dev-A audit pool (same database count; cost reported). Random-4 draws from the same candidate databases as targeted-4, so only the selection rule differs.
- **H3** The model fine-tuned on targeted-4-accepted samples has higher dev-B test-suite accuracy than the model fine-tuned on single-accepted samples, from the same warm start with matched example count, steps and approximate token budget.

Limitation stated in advance: verifier precision is measured on dev-A schemas and assumed to transfer to train schemas. As a check, 50 training-pool samples where single accepts and targeted-4 rejects are hand-labelled.

## Secondary hypotheses

- **S1** Targeted-4 false-accept share is within 1 percentage point of random-16.
- **S2** Held-out test-suite accuracy falls as known false accepts are mixed into training at 0, 25, 50% (P2, only if P0 and P1 finish).
- **E1 (exploratory)** False-accept mass rises more after single-filtered training than after targeted-filtered training. Prior work (ReViSQL; ved-2004 repo) observed flat rates; a null is expected and will be reported.

## Decision rules

- H1, H2, S1: paired comparison over the same samples; 95% interval from 10,000 bootstrap resamples of **questions** (samples of a question move together). Supported if the interval excludes 0 in the predicted direction; refuted if it excludes 0 in the other direction; otherwise inconclusive.
- H3: paired by held-out question; 95% bootstrap interval over questions, and a schema-level bootstrap reported alongside. Supported if the lower bound > 0; refuted if the upper bound < 0; inconclusive otherwise. A difference under 2 points is called "no practical difference" even if significant.
- One seed per arm is the P0 minimum; seed variation is reported only if P1 adds seeds. No claim generalises beyond Spider easy/medium and Tiny Aya Global.

## Data and exclusions (fixed before sampling)

- Spider easy and medium questions (official hardness script). Train-database questions only for warm start and pool; dev-database questions only for held-out evaluation.
- Excluded, counted and reported: gold queries that fail to execute; gold queries with LIMIT but no ORDER BY (result not determined); questions whose gold result is empty on every test-suite database; questions flagged in the gold audit as ambiguous or wrong.
- Pool size: *TBD-P0* questions × *TBD-P0* samples per question. Held-out size: *TBD-P0* (target ≥ 300 questions).

## What is not claimed

Not a new verification method; not online RL (training is reward-filtered supervised fine-tuning); not semantic equivalence; not results beyond the stated data and model.
