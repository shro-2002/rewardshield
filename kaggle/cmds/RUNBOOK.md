# P0 runbook (E02 → E05)

Kaggle allows one GPU job at a time on this account; jobs queue behind each other.

1. **E02 pool** (`e02a_pool.sh`, `e02c_pool.sh`, 2×T4). Download each with
   `kaggle kernels output sonika20000002/rewardshield-<slug> -p runs/E02/<slug>`.
   Check: no "Tool result for run_sql" inside assistant turns; 4 samples per question;
   train parts a (0-471), b (472-942), c (943-1199) concatenated into `runs/E02/pool_train.jsonl` (4,800 rows);
   `runs/E02/pool_devA.jsonl` (1,360 rows).
2. **E03** (CPU): `score_samples.py` on both pools (split files `train_pool_1200.jsonl`, `devA.jsonl`),
   `oracle_label.py` on the dev-A pool, `analyze.py verifiers`. Then label 100 verifier/oracle
   disagreements and 50 train samples where single accepts and targeted rejects (labels by Claude, disclosed).
3. **Arms**: `build_arm_sets.py --pool runs/E02/pool_train.jsonl --verdicts runs/E03/verdicts_train.jsonl
   --arms single-1 targeted-4 --out-dir runs/E04`, then `kaggle_job.py sync`.
4. **E04/E05** (`e04_e05_arms.sh`, 2×T4, `--datasets sonika20000002/rewardshield-e01-adapter`): trains both
   arms (masked loss, 100 × 16, seed 0) and runs greedy E04/E05 on dev-B plus E00/E01 re-runs on dev-A/dev-B.
   Then `oracle_label.py` on each output and `analyze.py arms --a E04 --b E05`.
