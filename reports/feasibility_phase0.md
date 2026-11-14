# Phase 0 feasibility report

Updated 2026-11-14 12:02 IST. Raw output: `runs/smoke_mac/smoke_report.json`.

| Check | Status | Evidence |
|---|---|---|
| Registration | Pass | User confirmed 2026-11-14 20:52 IST (registered before the Nov 8 close) |
| GPU: Kaggle | Pass (after weekly reset, 11:24 IST) | was blocked earlier: `kaggle kernels push`: "Maximum weekly GPU quota of 30.00 hours reached" |
| GPU: HF credits ($20 registration, $200 finalists) | **Needs user** | Paid compute + `hf auth login`; not attempted |
| Tiny Aya Global access | Pass | Kaggle Models copy (no HF token needed), CC BY-NC 4.0; HF repo is gated |
| Pinned environment | Pass | `env/manifest.md`, `uv.lock` |
| Model load + generation (Mac MPS, bf16) | Pass | 16.8 s load; correct SQL; 2.3 tok/s with PyTorch MPS |
| Generation (Mac MLX, bf16) | Pass | 12.3 tok/s generation, 328 tok/s prefill, 6.9 GB peak (short run) |
| Tool-call formatting | Pass, with note | Tiny Aya template does not render tools; AgentTune's fallback prompt works (1 tool call per question) |
| AgentTune SQL trajectory | Pass | 2 rollouts, correct answers, 48 s on MPS |
| AuditKIT import | Pass | `episode_from_openai_messages`: 5 events per episode (text, tool_call, observation) |
| LoRA training (MPS, bf16) | Pass | 3 steps, finite loss 3.02 → 2.98 |
| GPU smoke (Kaggle T4, fp16, Python 3.13) | Pass | 18 s load, 6.8 GB; LoRA losses finite (3.02 → 2.95); AgentTune `rollout_fn` 10.9 rollouts/min sequential (`runs/smoke_gpu/`) |
| Base-model tool use on T4 (greedy) | Weak | 0/2 tool calls: one answered in a code block, one wrote `tool_Name` (parser rejects); warm-start SFT must teach the format |
| Spider data and splits | Pass | train 5,864 / dev-A 340 / dev-B 379 questions, schema-disjoint |
| Test-suite oracle | Pass (rebuilt) | Official Drive file blocked; suites regenerated with Zhong et al.'s TestSuiteEval generator, 109 databases; 719/719 golds self-match, 50/50 wrong variants rejected (`oracle/ORACLE.md`) |
| HF artifact publication | **Needs user** | Not logged in to HF on this machine |

## Findings that change the plan

- The agent answers in prose after calling the tool, so the evaluated answer is the **last successfully executed SQL** in the trajectory, the same convention as AgentTune's `result_match_reward`.
- PyTorch MPS is too slow for the rollout pool. My estimate from MLX speed: about 12 s per two-turn rollout unbatched, so the planned ~4,000 rollouts would exceed 10 hours on the Mac. A GPU is on the critical path.
- T4 fp16 loads and trains with finite loss on short sequences; long-sequence training is verified by the E01 job.

## Go/no-go

Phase 0 **passed** on Kaggle at 11:59 IST (earlier: not passed: GPU throughput and the oracle are unverified. Verifier and data work (CPU) proceed; no expensive runs start until a GPU smoke test passes.)
The smoke benchmark's OOM came from loading a second model copy in the same process; SFT uses batch 1 × accumulation 16 at 3,072 tokens (prompt lengths: median 1,360, p90 2,071, max 3,247).
