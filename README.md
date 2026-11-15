# RewardShield: how reliable are execution rewards for a small database agent, and does it matter?

**One-line claim:** in a pre-registered, controlled study on Tiny Aya Global, checking SQL rewards on a few extra mutation-guided databases removes a small but replicated share of false accepts at equal cost; filtering self-generated training data with the better verifier did not measurably change the fine-tuned agent; and AgentTune's shipped SQL reward scores every Tiny Aya rollout −1, which we reproduce and patch.

**Links:** [code](https://github.com/shro-2002/rewardshield) · [HF models](https://huggingface.co/collections/shro-2002/rewardshield-models) · [HF data](https://huggingface.co/collections/shro-2002/rewardshield-data) · [results with all intervals and corrections](RESULTS.md) · [pre-registration](HYPOTHESES.md) · [decision log](DECISIONS.md) · [AgentTune issue #20](https://github.com/Lexsi-Labs/AgentTune/issues/20) / [PR #21](https://github.com/Lexsi-Labs/AgentTune/pull/21)


## Tracks and problem statements

- **Track 3, Agentic fine-tuning (AgentTune + AuditKIT)**
  - **9. Reward design and reward-hacking defences:** how often an execution reward accepts wrong SQL, what it costs to catch, and whether catching it changes what the agent learns.
  - **6. Data and database agents:** a Spider SQL agent rewarded on verified query results.

## Abstract

Execution rewards for SQL agents usually run the predicted and gold queries on one database and compare the rows. A wrong query that happens to return the same rows is rewarded, and a model trained on such rewards may learn it. We ran a controlled investigation of this for a small database agent: how often it happens, what catching it costs, which failure modes dominate, and whether better verification changes what the agent learns.

The agent is Tiny Aya Global (3B) answering Spider questions with one `run_sql` tool in AgentTune's format. Five verifiers were compared on 1,360 sampled trajectories, labelled by an independent test-suite oracle rebuilt with Zhong et al.'s own generator: single-database match (single-1), AgentTune's shipped `result_match_reward`, 4 random databases, 4 databases chosen to kill mutants of the gold query (targeted-4), and 16 random databases. Hypotheses, sample sizes and decision rules were registered before sampling.

On the dev-A audit pool, targeted-4 lowers the false-accept share from 3.88% (single-1) to 1.39% and beats random-4 at equal cost (H1, H2 supported). An independent audit showed the H2 size depended on one random draw of databases: averaged over 200 draws the gap is −0.25 points [−0.59, −0.00] on dev-A and −1.57 [−2.67, −0.60] on held-out dev-B outputs. On dev-B, false accepts are far more common, and most come from one schema (flight_2) whose whitespace-padded codes make gold results empty, a blind spot for every verifier.

Downstream, two LoRA SFT arms trained from the same warm start on 911 single-1-accepted or targeted-4-accepted self-generated samples reach 63.1% and 62.0% held-out test-suite accuracy (H3 inconclusive: −1.06 points [−4.22, +1.85]; minimum detectable effect about 4.3 points). A matched gold-trajectory control reaches 59.4%, no better than the 59.6% warm start, so the arms' gain is not explained by the extra training steps; it came through committing a query more often, not through better queries, and it is confounded with the source of the training data, so it does not isolate verification.

The toolkit contribution: RewardShield's verifiers run as a reward callable inside AgentTune's own rollout scoring, all evaluation episodes are scored through AuditKIT's agent evaluation (task success 51.5% → 63.1%, clean tool-call episodes 80.2% → 90.0%, batch-1 latency 5.7 → 4.9 s), and we found, reproduced and patched a defect that makes AgentTune's shipped SQL reward return −1 for every rollout under tool-blind chat templates such as Tiny Aya's.

## Headline before → after

| Held-out dev-B (379 questions, test-suite oracle) | Base (E00) | Gold warm start (E01) | Single-1 arm (E04) | Targeted-4 arm (E05) | Gold control (E07) |
|---|---|---|---|---|---|
| Test-suite accuracy (task success) | 51.5% | 59.6% | **63.1%** | 62.0% | 59.4% |
| Episodes committing an executed query | 80.2% | 84.4% | 90.0% | 89.2% | 85.0% |
| Correct given committed | 64.1% | 70.6% | 70.1% | 69.5% | 69.9% |
| Clean tool-call episodes (AuditKIT) | 80.2% | 84.4% | 90.0% | 89.2% | 85.0% |
| Latency, batch 1 (s/episode, T4) | 5.70 | 5.15 | 4.91 | 4.81 | 4.96 |

Verifier headline (false-accept share, lower is better): single-1 3.88% → targeted-4 1.39% on dev-A with the registered seeds (2.08% averaged over database draws); 12.1% → 7.9% on all dev-B greedy outputs.

## Base model and method in one line

Tiny Aya Global (3B, CC BY-NC 4.0) as a `run_sql` tool-calling agent in AgentTune's format; LoRA supervised fine-tuning with TRL on gold trajectories, then on self-generated trajectories filtered by each verifier; verifiers compared against an independent rebuilt Spider test-suite oracle. This is reward-filtered supervised fine-tuning, not reinforcement learning, and not AgentTune-native training.

## For judges: one minute

- **Solid:** git-timestamped pre-registration; an oracle independent in code; schema-disjoint splits; an external audit reproduced line by line; every negative result reported; a reproducibility script that re-derives every headline number.
- **Found:** targeted databases help a little and consistently (replicated on held-out schemas); one schema's data defect dominates false accepts; better verifier filtering did not change downstream accuracy at this scale; AgentTune's shipped SQL reward has a severe defect for small-model templates (issue [Lexsi-Labs/AgentTune#20](https://github.com/Lexsi-Labs/AgentTune/issues/20), patch [#21](https://github.com/Lexsi-Labs/AgentTune/pull/21)).
- **Corrected after the audit (original text kept, corrections dated):** H2 size (about 7× overstated on dev-A), "no practical difference" for H3, a confounded E04-vs-E01 gain, claims resting on LLM labels, and what the "agenttune" baseline measured.

## Problem statement and approach

**Why this problem / real use case.** Teams adapt small agents to their own databases with execution rewards because labels are expensive. If the reward accepts wrong queries, the agent trains on them and nothing in the training curve shows it. A cheap, measured check on reward reliability is useful before spending GPU on self-training or RL, and it should be measured on the agent's own samples, not on synthetic mutants.

**Approach.** (1) A fair agent setting: AgentTune's tool prompt, parser and tool-result format; batched rollouts with greedy parity to AgentTune's `rollout_fn` (12/12 identical). (2) Verifiers that differ only in database selection, all drawing on the same 24 generated candidate databases per question. (3) Labels from an independent oracle. (4) Matched SFT arms from one warm start, evaluated once on held-out schemas, plus a gold control. (5) An external audit, followed by exploratory analyses kept separate from the registered ones.

## Pre-registered hypotheses

From `HYPOTHESES.md` (committed 2026-11-14 before any model sampling; later changes only in its dated "Deviations" list):

| Hypothesis | Registered result | After the audit (exploratory) |
|---|---|---|
| **H1** targeted-4 has a lower false-accept share than single-1 (dev-A) | Supported, −2.48 [−4.16, −1.12] | holds by construction (targeted-4 includes the original database); seed-averaged −1.79 |
| **H2** targeted-4 lower than random-4 at the same database count | Supported, −1.74 [−3.30, −0.52] | seed-averaged −0.25 [−0.59, −0.00] dev-A; −1.57 [−2.67, −0.60] dev-B |
| **H3** targeted-4-filtered SFT beats single-1-filtered SFT on dev-B | Inconclusive, −1.06 [−4.22, +1.85] | minimum detectable effect ≈ 4.3 points; arms differ by 65 verifier-driven examples |
| **S1** targeted-4 within 1 point of random-16 | Not shown, +0.39 [−0.30, +1.33] | – |

## Threat model [T3]

The adversary is the training process itself: in self-training, any wrong query the reward accepts becomes a training target. We do not model a malicious user. Model SQL is untrusted: execution is read-only (an SQLite authorizer denies writes), time-limited, and capped in value, statement and result size.

## Related work

Zhong et al. 2020 (distilled test suites; single-database false positives of 3.6% easy / 5.9% medium on Spider, which our 3.88% matches); ReViSQL (Zhu et al., arXiv 2603.20004 v4): 32.8% of positive single-database rewards refuted by a formal checker, on BIRD with a large model, used as a soft reward penalty, without an ablation isolating that term; ved-2004/RLVR-Text-to-SQL (GRPO on Spider; single-database vs test-suite gap roughly constant); ParSEval, XData, VeriEQL (equivalence checking and test-database generation); AgentTune issue #11 / PR #12 (introduced `result_match_reward`). Targeted-k is a scaled-down, per-sample version of Zhong et al.'s distillation; we claim no new verification method. Not found after searching arXiv, lab blogs and GitHub (2026-11-14): a matched-cost targeted-vs-random comparison on model samples, or an isolated verifier ablation for small-model self-training.

## Hackathon repos used

### AgentTune (1.1.5)

- **Agent format:** the Tiny Aya tool fallback system prompt, `extract_tool_calls_from_text`, and the tool-result format, used by our batched rollouts (`src/rewardshield/rollout.py`, `agent.py`); greedy parity with `rollout_fn` checked (12/12).
- **Reward interface:** RewardShield's verifiers as an AgentTune reward callable, `f(completions, **kwargs) -> list[float]` with `result_match_reward`'s +2 / −1 scale (`src/rewardshield/agenttune_reward.py`). It runs inside AgentTune's own rollout scoring (`create_rollout_fn(reward_fn=...)`, driven by a `RolloutEngine` subclass that replays recorded turns; all 379 replayed E05 episodes reproduce the recorded final SQL) and through `combine_rewards`, the callable AgentTune's GRPO wrapper passes to TRL (`tests/test_agenttune_reward.py`, `scripts/demo_agenttune_reward.py`).
- **Baseline:** `result_match_reward`, measured as the "agenttune" verifier, plus an upstream issue and patch (see Findings).
- **Not used:** AgentTune's trainers. Training was raw TRL `SFTTrainer`, because `create_distill_trainer` renders trajectories differently from our rollouts (DECISIONS.md 2026-11-14 11:30). No GRPO run.

### AuditKIT (1.1.11)

All recorded dev-B evaluation episodes go through `auditkit.agent_eval` in recorded mode (`scripts/auditkit_eval.py`): `episode_from_openai_messages` (after un-folding Tiny Aya's user-turn tool results into tool turns), `AgentCase` with a `CustomPredicate` whose outcome is the oracle label, `AgentEvalRunner`, the metrics `tool_call_validity`, `redundant_tool_calls` and `agent_loop_detection`, and the targeted-4 verdict attached as `source_verdict` so AuditKIT records verifier/oracle disagreements (`reports/toolkit_metrics.md`). Not used: AuditKIT's LLM judges, deployed mode, repeated-trial reliability.

### How the repos connect

AgentTune defines the agent format and the reward interface → rollouts produce trajectories → RewardShield verifiers, running as AgentTune rewards, score them and select SFT data → TRL trains LoRA adapters → greedy evaluation trajectories → AuditKIT agent evaluation (task success, tool-call metrics, verifier/oracle disagreements) alongside measured latency and the independent oracle. Details and commands: `reports/upstream/INTEGRATION_NOTES.md`.

## Models and licenses

- **Base Aya model:** Tiny Aya Global (Kaggle Models `cohere-labs/tiny-aya/transformers/global/1`, the same checkpoint family as `CohereLabs/tiny-aya-global`), fp16 on T4, no quantisation. Licence: CC BY-NC 4.0 with Cohere's acceptable-use addendum, plus the Cohere Labs Acceptable Use Policy. Our LoRA adapters inherit these terms.
- **Labeller (not a training teacher):** Claude (Anthropic) wrote semantic labels for 89 dev-A disagreement rows and 50 transfer-check rows; disclosed, and used only for interpretive statements.

## Datasets, benchmarks and licenses

- **Source:** Spider 1.0 (Yu et al. 2018, CC BY-SA 4.0), easy and medium questions only (official hardness script).
- **Splits (schema-disjoint, seed 20261114):** train 5,864 questions on 146 databases (warm start: 1,500 gold trajectories on 73 databases; pool: 1,200 questions on the other 73); dev-A 340 questions / 10 databases (verifier audit); dev-B 379 / 10 (held-out evaluation, touched once per model).
- **Leak check** (exact match after whitespace and case normalisation; no embedding or MinHash check): no database is shared between splits. Six question strings recur across splits on different databases (generic counts such as "How many players are there?"). Two of them also have identical gold SQL text, and one ("What is the total number of airlines?", flight_4 in the warm-start data vs flight_2 in dev-B) was in the E01 training set, so at most 1 of 379 dev-B questions is affected.
- **Oracle:** test suites regenerated with Zhong et al.'s TestSuiteEval generator (unmodified, commit 7bf6378), 109 databases over 20 dev db_ids, compared with the official `exec_eval`. Not redistributed (the generator repository has no licence); `oracle/ORACLE.md` gives the rebuild steps.

## Tool / task environments, trajectories [T3]

One tool, `run_sql(sql_command)`: read-only SQLite, up to 10 rows returned, at most 4 agent steps. The evaluated answer is the last successfully executed query. Trajectories (system, user, assistant tool calls, tool results, final reply) are released for every pool and evaluation run, with oracle labels and batch-1 timings.

## Metrics, and why these

| Metric | Direction | Why |
|---|---|---|
| False-accept share (wrong accepts / accepts) | lower | what a trainer actually ingests |
| False-accept mass, false-reject rate | lower | contamination per sample; correct data lost |
| Verification cost (ms/sample, SQL runs/sample, construction s/question) | lower | matched-cost comparison |
| Test-suite accuracy (oracle) = task success | higher | held-out correctness |
| Commit rate, correct given committed | higher | separates finishing from correctness |
| Clean tool-call episodes (tool-call accuracy) | higher | at least one parsed `run_sql` call, no rejected call attempt, every call executed without error; also call execution rate. AuditKIT's `tool_call_validity` is 100% for every model and uninformative with one tool |
| Average latency | lower | measured wall-clock seconds per episode at batch 1 (60 dev-B questions, one T4, fp16); batch-16 throughput reported separately; verifier CPU time reported separately and never added |

**Checking the automatic judge.** The main judge is the oracle, checked by sanity tests (719/719 golds self-match; 50/50 hand-made wrong variants rejected) and against blind Claude labels (no equivalent query ever rejected; 94% agreement when nullable foreign keys are treated as total, 71% under the strict reading). A union-oracle sensitivity check and an inspection of every sample our own 25 databases reject but the oracle accepts found 8 genuine misses out of 54 (RESULTS.md E-7). A 60-row blind human-label set is prepared with a scorer for Cohen's κ; **human labels had not been collected at submission time**, so no κ is reported and LLM labels support no headline claim.

## Method / experiments

Hyperparameters per run: `DECISIONS.md`, `kaggle/cmds/`, and each adapter's `train_summary.json`.

- **E01 warm start:** LoRA r16, alpha 32, dropout 0.05 on all attention and MLP projections; 150 steps × 16, lr 1e-4 cosine, 5% warmup, seed 0. Loss also fell on tool-result turns, a bug that taught the model to write fake tool results; it was fixed for every later run, and all affected evaluations were re-run and reproduced.
- **E02 pools:** E01, temperature 0.8, 4 samples per question; 1,182 training questions (the 18 `baseball_1` questions excluded for length) and 340 dev-A questions.
- **E04/E05 arms and E07 control:** from E01, masked loss (assistant turns only), 100 steps × 16, lr 1e-4, seed 0, 2×T4 DDP; 911 examples each.
- **Evaluation:** greedy, batch 16, fp16, at most 4 steps, 192 new tokens per turn.
- **AgentTune and AuditKIT:** defaults except as listed above.
- **Seeds:** one per run.

## Results

### Same model before vs after

See the headline table. Paired dev-B differences (95% bootstrap, questions; schema-level intervals in RESULTS.md):

| Comparison | Difference (points) | 95% CI |
|---|---|---|
| H3: E05 − E04 | −1.06 | [−4.22, +1.85] |
| E04 − E01 | +3.43 | [+0.79, +6.07] |
| E07 − E01 (same recipe, gold data) | −0.26 | [−3.43, +2.90] |
| E04 − E07 | +3.69 | [+0.26, +7.12] (schema-level [−0.95, +8.16]) |
| E05 − E07 | +2.64 | [−0.26, +5.54] |
| E05 − E00 | +10.55 | [+5.80, +15.30] |

**What E07 controls and what it does not.** E07 holds fixed the starting checkpoint, the question set (869 of its 911 questions are shared with both arms), steps, batch, learning rate, loss mask, seed, token budget (2.18 M vs 2.18 / 2.17 M) and evaluation. So the arms' gain over E01 is not explained by extra training on these questions. E07 does not hold fixed the source of the training trajectories: the arms train on the model's own verifier-accepted samples, which may make several calls, end in the model's own words, and include a few percent of wrong queries; E07 trains on gold trajectories with exactly one call and a templated reply. E04/E05 − E07 therefore measure "self-generated filtered data vs gold data" with these factors bundled, and say nothing about verification alone. The only contrast where verification alone differs is H3, which is inconclusive.

### Agentic trajectory metrics [T3] (AuditKIT, dev-B, 379 episodes per model)

| Model | Task success | Clean-episode rate | Call execution rate | Batch-16 s/episode (throughput) | Batch-1 latency (s/episode) |
|---|---|---|---|---|---|
| E00 base | 51.5% | 80.2% | 80.2% | 3.41 | 5.70 |
| E01 warm start | 59.6% | 84.4% | 84.7% | 2.39 | 5.15 |
| E04 single-1 arm | 63.1% | 90.0% | 90.7% | 2.34 | 4.91 |
| E05 targeted-4 arm | 62.0% | 89.2% | 89.4% | 2.42 | 4.81 |
| E07 gold control | 59.4% | 85.0% | 85.4% | 2.24 | 4.96 |

Latency tracks generated length (86 tokens per episode for the base model vs 69-74 for the adapters, at 0.066-0.072 s per token). Verifier execution time is separate: 0.09-0.10 ms (single-1) and 0.28-0.32 ms (targeted-4) per episode on a laptop CPU, plus about 0.05 s per question to build the databases. AuditKIT found no redundant calls or loops in any model.

### Verifier audit (dev-A pool, 1,360 samples, registered seeds)

| Verifier | Accepts | FA share | FR rate | ms/sample | SQL runs |
|---|---|---|---|---|---|
| single-1 | 748 | 3.88% | 0.00% | 0.09 | 1 |
| agenttune rule (shipped) | 720 | 4.31% | 4.17% | – | 1 |
| random-4 | 734 | 3.13% | 1.11% | 0.31 | 4 |
| targeted-4 | 717 | 1.39% | 1.67% | 0.29 | 4 |
| random-16 | 700 | 1.00% | 3.62% | 1.08 | 16 |

### Findings

1. **Targeted selection helps a little, consistently.** Seed-averaged H2: −0.25 points on dev-A, −1.57 on held-out dev-B (24 vs 4 questions favour targeted-4). The mutation step chooses a database on only about a third of questions; with a single random draw, targeted-4 beats random-4 on dev-A in only 67% of draw pairs.
2. **Verifier comparisons need seed averaging.** The registered pair of random draws sat in opposite tails of their distributions, inflating the dev-A H2 gap about 7×. The seeds were committed before sampling, so this was chance, not selection.
3. **Population definitions change rates a lot.** Dev-B single-1 false-accept share is 12.1% over all 1,516 greedy outputs and 18.1% over the 845 distinct (question, SQL) pairs, because deduplication keeps 79% of wrong accepts but only 49% of correct ones. Per model it is 10.0-14.5%. Both numbers are correct; the per-model rows describe a single policy (RESULTS.md E-9).
4. **One data defect dominates held-out false accepts.** flight_2 stores whitespace-padded codes, so its own foreign-key join matches nothing and 34 gold queries return empty sets or zeros. The 45 degenerate dev-B questions hold 65-67 of every verifier's 71-123 false accepts; without them targeted-4's share is 1.2% and single-1's 6.3%. Our generator inherits the problem and also fails to seed double-quoted string literals. The benchmark was not changed.
5. **Better filtering did not change the trained agent** at this dose. The extra SFT on self-generated data raised commit rate (about 85% → 90%), not correctness given a committed query (about 70% throughout), and gold data with the same recipe did not.
6. **AgentTune's shipped `result_match_reward` has concrete defects.** A self-contained repro (`reports/upstream/result_match_reward_repro.py`, 8/8 checks) shows column-order false rejects (4.2% of correct dev-A samples), single-database false accepts, row order ignored under `ORDER BY`, exact float comparison and a side-effect log write. The most serious is a score of −1 for every rollout when the chat template has no tool role (Tiny Aya's case), because AgentTune folds tool results into user turns. Our E03 "agenttune" column therefore measures the comparison rule, not in-loop behaviour. Filed upstream as [Lexsi-Labs/AgentTune#20](https://github.com/Lexsi-Labs/AgentTune/issues/20) with patch [Lexsi-Labs/AgentTune#21](https://github.com/Lexsi-Labs/AgentTune/pull/21).

### What didn't work (negative results)

- H3 is inconclusive and S1 was not shown.
- E07 shows no gain from extra gold-data SFT.
- The warm start initially learned to write fake tool results; this was fixed and all evaluations re-run.
- The official test-suite download was blocked, so the oracle is a smaller rebuild.
- A pre-registered exclusion was not applied to 3 dev-B questions; applying it changes no verdict.

### Confidence intervals

All intervals are 95% bootstrap over questions (10,000 resamples), with schema-level intervals alongside. Seed-averaged analyses use 200 draws × 5,000 resamples.

### Sample inputs and outputs

Every trajectory is in the trajectories dataset. A real false accept from the flight_2 blind spot (dev-B `dev-dev-00198`, E04):

- Question: "Give the city and country for the Alton airport."
- Gold: `SELECT City, Country FROM AIRPORTS WHERE AirportName = "Alton"` returns no rows, because every stored airport name ends with a space (`'Alton '`).
- Model: `SELECT city, country FROM airports WHERE airportcode = "ALT"` also returns no rows, so the results match and single-1 accepts it, even though it filters on a different column. The test-suite oracle rejects it (its generated databases make the two queries differ).

### Compute used

- **GPU:** Kaggle 2×T4 sessions, about 9.2 recorded hours (smoke 0.07, E01 job 0.8, warm-start SFT 2.1, pools 2.2, arms 2.7, E07 1.3), plus some E02 jobs deleted after the fake-tool-result bug, whose time was not logged.
- **CPU:** one Apple M4 laptop for verifiers, the oracle and all analyses.
- **Cost:** no paid compute.

## Limitations

- One seed per run, ten schemas per dev split, Spider easy and medium only, one 3B model.
- The oracle is a rebuild with 2-12 databases per schema and shares its method family with targeted-k. A union-oracle check keeps H1 and H2 supported and leaves H3 unchanged.
- The database generator has known defects: double-quoted literals are not seeded, composite keys can hold NULL, and NOT NULL foreign keys can dangle. They were found after the registered analyses and are not fixed for Round 1.
- Disagreement-only labelling hides misses that every verifier accepts. The LLM labels come from one rater and have not been checked against human labels.
- Dev-A false-accept rates are far below dev-B's; absolute rates do not generalise across schemas, policies or population definitions.
- Training is reward-filtered SFT, not RL; results may not carry over to online RL, where false accepts compound.
- E07 does not isolate verification (see Results).

## With more credits

**Planned approach** (`reports/round2_E09_prereg.md`, written before any Round 2 data):

1. **Oracle labels on the training schemas.** Build test suites for the training databases with the same generator and fix our own candidate generator first.
2. **E09-R2, coupled dose-response.** Nested arms that share one question set and one correct sample per question, replacing 0 / 4 / 12 / 25% of them with oracle-wrong, single-accepted samples; three seeds per dose; evaluation on all 719 dev questions.
3. **A pre-registered degenerate-gold guard.**
4. **E10:** GRPO with each verifier as the reward through AgentTune's trainer, gated on a 1-GPU-hour smoke test.

**Expected before / after** (forecasts, not results):

- **E09-R2:** a monotone decline of roughly 1-3 points in held-out accuracy from 0% to 25% contamination, within reach of the pooled design's minimum detectable effect of about 2.5 points.
- **Degenerate-gold guard:** false-accept shares on dev-B close to the 1-6% seen without flight_2's degenerate questions.
- **E10:** targeted rewards growing false-accept mass more slowly than single-database rewards during GRPO.

## Artifacts

- **HF datasets collection:** https://huggingface.co/collections/shro-2002/rewardshield-data, three separately licensed repositories (Spider splits and gold trajectories; agent trajectories; verdicts, labels, metrics and logs).
- **HF models collection:** https://huggingface.co/collections/shro-2002/rewardshield-models, with LoRA adapters for E01, E04, E05 and E07.
- **GitHub repo:** https://github.com/shro-2002/rewardshield
- **Upstream contribution:** issue [Lexsi-Labs/AgentTune#20](https://github.com/Lexsi-Labs/AgentTune/issues/20) and patch [Lexsi-Labs/AgentTune#21](https://github.com/Lexsi-Labs/AgentTune/pull/21).

## Documentation and reproduction

The repository guide below covers the layout, environment (Python 3.12, `uv sync`, `uv.lock`) and exact commands. `scripts/repro_check.py` re-derives every headline number from the released artifacts and runs the test suite. GPU steps ran on Kaggle 2×T4 with the commands in `kaggle/cmds/`.

## Declaration of work done outside the hackathon

None. All code, data processing and experiments were done between 2026-11-14 and 2026-11-16. Third-party code is either vendored with its licence (test-suite-sql-eval, Apache-2.0) or used unmodified and not redistributed (TestSuiteEval). AgentTune and AuditKIT are pip dependencies.

## Teammates

Solo submission.

## LLM usage statement

Claude (Anthropic) was used throughout, under the author's direction, and the author reviewed and approved the decisions. We do not state a percentage because none was measured. Claude's actual contributions:

- **Code:** wrote most of the code in this repository, including the verifiers, oracle tooling, rollout and training scripts, analyses, the AgentTune and AuditKIT integration, and the upstream patch.
- **Text:** drafted most documentation, including this write-up.
- **Labels and review:** produced the disclosed semantic labels, and a separate Claude session performed the independent audit whose scripts are included.
- **Not Claude's:** the human blind-label set is reserved for the author.

## References

See Related work and the links in Artifacts.

## Repository guide

### Layout

| Path | What it is |
|---|---|
| `src/rewardshield/sqlexec.py` | read-only, time- and size-capped SQLite execution; result matching |
| `src/rewardshield/dbgen.py`, `mutants.py`, `verifiers.py` | candidate databases, gold-query mutants, single / random-k / targeted-k verifiers |
| `src/rewardshield/agenttune_reward.py` | the verifiers as an AgentTune reward callable |
| `src/rewardshield/agent.py`, `rollout.py`, `sft_mask.py` | AgentTune-format agent, batched rollouts, assistant-only loss mask |
| `oracle/` | independent test-suite oracle rebuilt with Zhong et al.'s generator (see `oracle/ORACLE.md`) |
| `scripts/` | splits, rollouts, scoring, oracle labelling, arm building, SFT, analysis, Kaggle jobs, AuditKIT evaluation, HF packaging |
| `scripts/exploratory/` | post-hoc analyses, including the independent audit scripts (not pre-registered) |
| `kaggle/cmds/` | the exact GPU job commands |
| `tests/` | unit and integration tests (`uv run pytest -q`) |
| `reports/` | toolkit metrics, upstream issue draft and repro, Round 2 pre-registration |
| `data/splits/` | schema-disjoint splits (train, pool, dev-A, dev-B) |

Not in git: Spider databases, the rebuilt oracle databases (generator has no licence), model weights, run outputs.
Run outputs (pools, verdicts, labels, trajectories, adapters, logs) are in the Hugging Face collections above.

### Check the headline numbers from a fresh clone

```bash
uv sync
```

```bash
uv run python scripts/fetch_artifacts.py --user shro-2002
```

```bash
uv run python scripts/repro_check.py
```

`fetch_artifacts.py` puts every released file back at its original path; `repro_check.py` runs the tests and re-derives the verifier, H1-H3 and E07 numbers (`--with-exploratory` also re-runs the seed-averaged audit, which needs the Spider databases).

### Reproduce

Environment: Python 3.12, [uv](https://docs.astral.sh/uv/), versions pinned in `uv.lock` (AgentTune 1.1.5, AuditKIT 1.1.11, TRL 1.7.1, transformers 5.23).

```bash
uv sync
```

```bash
uv run pytest -q
```

CPU steps (Mac or Linux; Spider unpacked at `data/raw/spider_zip/spider`):

```bash
uv run python scripts/build_splits.py
uv run python scripts/build_sft_gold.py --n-warm 1500 --out runs/E01
uv run python scripts/bench_verifiers.py
```

GPU steps ran on Kaggle 2×T4 through `scripts/kaggle_job.py` with the commands in `kaggle/cmds/` (E01 warm start, E02 pools, E04/E05 arms, E07 control). Then, on CPU:

```bash
uv run python scripts/score_samples.py --help
uv run python scripts/oracle_label.py --help
uv run python scripts/build_arm_sets.py --pool runs/E02/pool_train.jsonl --verdicts runs/E03/verdicts_train.jsonl --arms single-1 targeted-4 --out-dir runs/E04
uv run python scripts/analyze.py --help
uv run python scripts/auditkit_eval.py --help
```

Exploratory reproduction of the audit (dev-B suites go to a scratch directory):

```bash
uv run python scripts/exploratory/audit5.py /tmp/rs_devB_suites
```

The oracle needs its own environment (`oracle/ORACLE.md`) and `PYTHONHASHSEED=0`.

### Licences

Code in this repository: MIT (see `LICENSE`). Vendored `third_party/test-suite-sql-eval`: Apache-2.0. Spider: CC BY-SA 4.0.
Tiny Aya Global and our adapters: CC BY-NC 4.0. AgentTune and AuditKIT are used as pip dependencies under the Lexsi Labs
Source Available License and are not redistributed here.
