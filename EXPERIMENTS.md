# Experiment registry

Every run gets an ID, config path, seed, checkpoint and result record. Status: planned, running, done, failed, dropped.

| ID | Priority | Description | Config | Seed | Checkpoint / output | Status |
|---|---|---|---|---|---|---|
| P0-SMOKE-MAC | P0 | Load, generate, AgentTune rollout, AuditKIT import, LoRA step on M4 (MPS) | `scripts/smoke_phase0.py` | – | `runs/smoke_mac/` | done |
| P0-SMOKE-GPU | P0 | Same on Kaggle T4, fp16; throughput | `scripts/smoke_phase0.py --dtype float16` | – | `runs/smoke_gpu/` | done |
| E00-BASE | P0 | Base Tiny Aya Global, greedy, dev-A and dev-B | Kaggle `rewardshield-e01` v2 | 0 | `runs/E01_job/E00_*.jsonl` | done (old loop): dev-A 47.9%, dev-B 51.5%; re-run 05:08 reproduces it exactly |
| E01-SFT | P0 | Gold-trajectory SFT warm start, 150 steps × 16, LoRA r16 | Kaggle `rewardshield-e01-sft` v2 (v1: DataParallel crash) | 0 | `runs/E01_sft/E01_adapter`; Kaggle dataset `rewardshield-e01-adapter` | done (old loop, fake tool results): dev-A 61.8%, dev-B 59.6%; re-run 05:08 reproduces it exactly |
| E02-POOL | P0 | E01 rollouts, n=4, T=0.8: training pool 1,200 train questions; audit pool 340 dev-A | Kaggle `rewardshield-e02-pool`; `train_pool_1200.jsonl`, `devA.jsonl` | 0 | `runs/E02/` | re-pushed 22:55 with stop-token fix (P100 + 2×T4) |
| E03-STATIC | P0 | Static verifier comparison on E02 (single, agenttune, random-k, targeted-k) vs oracle | `scripts/score_samples.py`, `analyze.py verifiers` | – | `runs/E03/` | done: H1, H2 supported; S1 not shown |
| E04-SFT-SINGLE | P0 | E01 + SFT on single-accepted samples (911) | Kaggle `rewardshield-e04-arms` | 0 | `runs/E04/` | done: dev-B 63.1% |
| E05-SFT-TARGETED | P0 | E01 + SFT on targeted-4-accepted samples (911) | Kaggle `rewardshield-e04-arms` | 0 | `runs/E04/` | done: dev-B 62.0%; H3 inconclusive |
| E06-SFT-RANDOM | P1 | E01 + SFT on random-4-accepted samples | – | 0 | – | dropped for Round 1 (2026-11-15): E04 and E05 are already indistinguishable, a third arm between them cannot be read |
| E07-CONTROL | P1 | E01 + 100 × 16 masked-loss steps on gold trajectories for a matched 911-question set; plus batch-1 latency probe for E00/E01/E04/E05/E07 | `kaggle/cmds/e07_control.sh`, `scripts/build_e07_control.py`, DECISIONS.md 2026-11-15 10:05 | 0 | `runs/E07/` | done: dev-B 59.4% (E07 − E01 −0.26 [−3.43, +2.90]; E04 − E07 +3.69 [+0.26, +7.12]); batch-1 latency 4.8-5.7 s/episode |
| E08-SEEDS | P1 | Extra seeds for E04, E05 | – | 1 | – | deferred to Round 2: cannot make H3 conclusive at a 4.3-point detectable effect |
| E09-DOSE | P2 | Contamination 0/25/50% | – | 0 | – | infeasible as registered; redesigned as E09-R2 for Round 2 (`reports/round2_E09_prereg.md`) |
| E10-GRPO | P2 | Online GRPO pilot | – | 0 | – | Round 2 only, gated on a 1-GPU-hour smoke test |
