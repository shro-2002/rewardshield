# Experiment registry

Every run gets an ID, config path, seed, checkpoint and result record. Status: planned, running, done, failed, dropped.

| ID | Priority | Description | Config | Seed | Checkpoint / output | Status |
|---|---|---|---|---|---|---|
| P0-SMOKE-MAC | P0 | Load, generate, AgentTune rollout, AuditKIT import, LoRA step on M4 (MPS) | `scripts/smoke_phase0.py` | – | `runs/smoke_mac/` | done |
| P0-SMOKE-GPU | P0 | Same on Kaggle T4, fp16; throughput | `scripts/smoke_phase0.py --dtype float16` | – | `runs/smoke_gpu/` | done |
| E00-BASE | P0 | Base Tiny Aya Global, greedy, dev-A and dev-B | Kaggle `rewardshield-e01` v2 | 0 | `runs/E01_job/E00_*.jsonl` | done: dev-A 47.9%, dev-B 51.5% |
| E01-SFT | P0 | Gold-trajectory SFT warm start, 150 steps × 16, LoRA r16 | Kaggle `rewardshield-e01-sft` v2 (v1: DataParallel crash) | 0 | `runs/E01_sft/E01_adapter`; Kaggle dataset `rewardshield-e01-adapter` | done: dev-A 61.8%, dev-B 59.6% |
| E02-POOL | P0 | E01 rollouts, n=4, T=0.8: training pool 1,200 train questions; audit pool 340 dev-A | Kaggle `rewardshield-e02-pool`; `train_pool_1200.jsonl`, `devA.jsonl` | 0 | `runs/E02/` | running |
| E03-STATIC | P0 | Static verifier comparison on E02 (single, agenttune, random-k, targeted-k) vs oracle | – | – | – | planned |
| E04-SFT-SINGLE | P0 | E01 + SFT on single-accepted samples | – | 0 | – | planned |
| E05-SFT-TARGETED | P0 | E01 + SFT on targeted-4-accepted samples | – | 0 | – | planned |
| E06-SFT-RANDOM | P1 | E01 + SFT on random-4-accepted samples | – | 0 | – | planned |
| E07-CONTROL | P1 | E01 + equal steps on gold trajectories | – | 0 | – | planned |
| E08-SEEDS | P1 | Extra seeds for E04, E05 | – | 1 | – | planned |
| E09-DOSE | P2 | Contamination 0/25/50% | – | 0 | – | planned |
| E10-GRPO | P2 | Online GRPO pilot | – | 0 | – | planned |
