# E09-R2: contamination dose-response with coupled sampling (Round 2 pre-registration draft)

Status: **draft, written 2026-11-15 before any E09-R2 data exists.** Replaces the Round 1 E09 sketch
(HYPOTHESES.md S2, "0/25/50% known false accepts"), which the audit showed to be infeasible: only about
180 oracle-known false accepts exist, all on dev-A schemas, which may not enter training. Frozen on the
day Round 2 starts; changes after that go in a dated "Deviations" list.

## Question

Does training on executed-but-wrong SQL that a single-database reward accepts lower held-out accuracy,
and from what contamination level? H3 could not answer this: the E04 and E05 arms differed by 65 of 911
examples, and the minimum detectable effect of that comparison was about 4.3 points.

## Design changes from Round 1

1. **Labels on training schemas.** Build an independent test suite for the training-pool databases with the
   same unmodified TestSuiteEval generator used for the dev oracle (capped as in `oracle/ORACLE.md`), and
   label every training-pool sample. "Wrong" then means oracle-wrong, not "rejected by our own verifier".
   A degenerate-gold guard is applied before sampling: questions whose gold result is empty, all-zero or
   all-NULL on the original database are excluded and counted (the flight_2 blind spot). Before any Round 2 sampling, the candidate-database generator is fixed and re-frozen: double-quoted string constants are seeded (with whitespace-trimmed variants), composite primary keys reject NULL, and NOT NULL foreign keys are only filled from existing parent rows (RESULTS.md E-6, E-7).
2. **Coupled sampling.** Fix one question set Q (all pool questions with at least one oracle-correct and one
   oracle-wrong, single-accepted sample). Draw one random order of Q (seed 20261116). Every arm uses the same
   questions and the same oracle-correct sample per question; arm at dose p replaces the samples of the first
   ⌈p·|Q|⌉ questions in that order with one of their oracle-wrong, single-accepted samples. Arms are nested,
   so two adjacent doses differ only in the replaced questions.
3. **Realistic doses.** p ∈ {0, 0.04, 0.12, 0.25}: 0 = clean (the E07 role), 0.04 ≈ single-1 false-accept
   share on the dev-A pool, 0.12 ≈ the share on dev-B greedy outputs (12.5-18% depending on verifier), 0.25 as
   an upper anchor. Arm size is fixed by |Q| after the guard; if |Q| < 400 the 0.25 arm is dropped first.
4. **Power.** Evaluate on dev-A and dev-B together (719 questions; dev-A was used to tune verifiers, never to
   select models) and train 3 seeds per dose (12 runs, about 1 GPU hour each on 2×T4, plus evaluation).

## Hypotheses (directional, fixed before data)

- **D1** Held-out test-suite accuracy decreases with dose: the slope of accuracy on p, fitted over the four
  doses and three seeds, is negative. 95% interval from 10,000 bootstrap resamples of questions (seeds kept
  together). Supported if the upper bound < 0; refuted if the lower bound > 0; otherwise inconclusive.
- **D2** Accuracy at p = 0.12 is lower than at p = 0 (paired by question, averaged over seeds). Same rule,
  plus "no practical difference" only if the whole interval lies inside ±2 points.
- **D3 (exploratory)** Among wrong samples learned at high dose, the model's held-out errors repeat the same
  error type (operator class from `mutants.py`) more often than at p = 0.

## Fixed analysis details

Same prompt, loop, decoding (greedy), LoRA settings and E01 starting checkpoint as E04/E05/E07, masked loss,
100 steps × 16, lr 1e-4. Report tokens seen per arm, commit rate and correctness-given-committed alongside
accuracy (the Round 1 arms moved commit rate, not correctness). Union-oracle and degenerate-gold
sensitivity analyses are reported, labelled as sensitivity. No result is dropped.

## What this does not test

Online RL. The E10 GRPO pilot stays a separate Round 2 item, gated on a 1-GPU-hour smoke test.
