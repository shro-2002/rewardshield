# RewardShield

A controlled measurement study of SQL execution-reward reliability for a small agent: how often single-database
rewards accept wrong SQL, what extra test databases cost, and whether filtering self-generated training data with a
better verifier changes the fine-tuned agent. Tiny Aya Global (3B) on Spider, Lexsi AI Safety and Alignment
Hackathon, Track 3 (AgentTune + AuditKIT).

- Write-up: [WRITEUP.md](WRITEUP.md)
- Results with intervals, corrections and exploratory analyses: [RESULTS.md](RESULTS.md)
- Pre-registration: [HYPOTHESES.md](HYPOTHESES.md); decision log: [DECISIONS.md](DECISIONS.md); run registry: [EXPERIMENTS.md](EXPERIMENTS.md)

## Layout

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
Run outputs (pools, verdicts, labels, trajectories, adapters, logs) are in the Hugging Face collections linked in WRITEUP.md.

## Reproduce

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

## Licences

Code in this repository: MIT (see `LICENSE`). Vendored `third_party/test-suite-sql-eval`: Apache-2.0. Spider: CC BY-SA 4.0.
Tiny Aya Global and our adapters: CC BY-NC 4.0. AgentTune and AuditKIT are used as pip dependencies under the Lexsi Labs
Source Available License and are not redistributed here.
