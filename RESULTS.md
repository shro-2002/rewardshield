# Results

No results yet. Every number here must point to a run ID in `EXPERIMENTS.md` and a file under `runs/`.
Negative and inconclusive results are reported with the same prominence as positive ones.

## Phase 1 adversarial benchmark (not a hypothesis test)

Run `runs/bench_devA/` (`scripts/bench_verifiers.py`), 2026-11-14 02:05 IST. Input: one-change mutants of the 340 dev-A **gold** queries, deliberately adversarial and kept separate from model samples. 330 mutants are indistinguishable from gold on the original database. Some may be truly equivalent to gold, so "accepted" is not automatically an error; the oracle has not scored them.

| Verifier | Mutants accepted (of all generated) | Median verify ms |
|---|---|---|
| single | 254 | 0.104 |
| random-4 | 158 | 0.117 |
| targeted-4 | 97 | 0.104 |
| random-16 | 101 | 0.114 |

Construction: 24 candidate databases per question, median 0.05 s, 66.8 s for all 340 questions on the M4 CPU.
Caveat: targeted selection is greedy over the same mutant operators used here, so this table favours targeted by construction. H1 and H2 are tested only on model samples labelled by the oracle.
