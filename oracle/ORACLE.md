# Independent test-suite oracle (Option A)

Built 2026-11-14. Option A (regenerate test suites with the original authors' generator) worked. Option B (ParSEval) was not needed and was not attempted.

## What it is

- `oracle/oracle.py`: `oracle_match(db_id, gold, pred) -> bool | None` plus the CLI `python oracle/oracle.py --pairs pairs.jsonl --out verdicts.jsonl [--workers N]`. It calls the vendored official `third_party/test-suite-sql-eval/exec_eval.py::eval_exec_match` over `data/oracle/test_suite/<db_id>/` with `keep_distinct=True` and `plug_value=False`. That evaluator compares results on every `*.sqlite` file in the directory. It uses bag semantics, treats order as significant when the gold has `ORDER BY`, and searches over column permutations.
  - It returns `None` when the db_id has no suite, or when the gold itself fails on a suite database (the official evaluator raises an assertion in that case).
  - It returns `False` for an empty prediction and for a prediction that errors or times out on any suite database.
- `oracle/build_suite.py`: regenerates the suites (see below).
- `oracle/sanity.py`: runs the sanity checks. Its outputs are in `oracle/sanity_out/report.json` and `oracle/sanity_out/mutants.jsonl`.
- `data/oracle/test_suite/<db_id>/<db_id>.sqlite` (the Spider original) plus `<db_id>1.sqlite`, `<db_id>2.sqlite`, and so on. This is the same layout as the official suite.
- `data/oracle/manifest.json`: for each db, the candidate counts and statuses, the suite size, the mapping from suite file to candidate, and timings. For each gold, the neighbor count, the number of neighbors left undistinguished, and the selected databases.

It is independent of our verifier: nothing is imported or copied from `src/rewardshield/`.

## Sources, commits, licenses

| Component | Source | Commit / version | License |
|---|---|---|---|
| Generator (fuzzer, neighbor queries, `result_eq`) | https://github.com/ruiqi-zhong/TestSuiteEval cloned into `oracle/TestSuiteEval` | `7bf637883cf092867d33f58ee6f365f5a05e0ee2` (2020-12-01) | **No LICENSE file in the repo** (all rights reserved by default). Fine for research use here, but do not redistribute the code. Check with the authors before shipping the generated DBs. |
| Comparison | vendored `third_party/test-suite-sql-eval` | `e97acc546ecbee8fa27fa8dbf025ef61493a876c` | Apache-2.0 |
| Data | Spider 1.0 dev databases | from `data/raw/spider_zip` | CC BY-SA 4.0 |
| Runtime | `oracle/.venv` (uv, 23 MB) | Python 3.11.15, sqlparse 0.4.4, numpy 2.4.6, tqdm 4.70.1 | |

## Patches

**No file in `oracle/TestSuiteEval` or `third_party/` was modified.** The 2020 code runs unchanged on Python 3.11 with sqlparse 0.4.4 and numpy 2.x. Every adaptation lives in our own scripts:

1. **VACUUM after each candidate** (`build_suite.py`). The authors' writer (`init_empty_db_from_orig_`) copies the full original and then DROPs the tables without VACUUM. As a result every wta_1 candidate was about 100 MB of free pages, which is what filled the disk in the first run (54 GB). After VACUUM the selected candidates are 16 to 112 KB.
2. **Private copies of the originals** (`data/oracle/_orig`, deleted after use). The generator writes temporary files next to its input database, so this keeps it from writing into `data/raw`.
3. **In-process execution with a timeout during distillation** (`run_sql` in `build_suite.py`). It mirrors `sql_util.run.exec_db_path_` (the same `replace_cur_year` and `text_factory`) and adds a sqlite progress-handler deadline. The authors' `exec_db_path` instead spawns one Python subprocess per query, which is too slow and has no usable cap.
4. **Timeout in the oracle** (`oracle.py`). The official `exec_on_db` timeout (`asyncio.wait_for` around blocking code) never fires. `oracle.py` therefore wraps `exec_eval.get_cursor_from_path` at runtime with a 10 s per-query progress-handler deadline. An interrupted query surfaces as an ordinary execution exception, so the prediction is judged wrong.
5. **`PYTHONHASHSEED=0` is required**, because the fuzzer iterates over Python sets of values. The script refuses to run without it.

## Generation procedure and parameters

For each db_id, processed one at a time:

1. Sample K candidates with `fuzz.fuzz.generate_random_db_with_queries_wrapper`. The fuzzing constants come from **all** Spider-dev gold queries of that db, as the authors' `DBFuzzer` does.
2. VACUUM each candidate. Discard any candidate over 20 MB (none were).
3. Drop a candidate if any devA/devB gold errors on it or takes more than 2 s (none were dropped).
4. For each unique devA/devB gold query (379 of them, covering all 719 questions), generate neighbors with `fuzz.neighbor.generate_neighbor_queries_path`. Then run the greedy distillation from the authors' `demo.ipynb` over the candidates in index order: a candidate is kept if it distinguishes at least one still-undistinguished neighbor under `sql_util.eq.result_eq`, with `order_matters = 'order by' in gold`. Each neighbor execution is capped at 0.5 s; a neighbor that times out 3 times is dropped (this never happened). Each query has a 600 s budget.
5. Suite = original plus the union of kept candidates. Every unselected candidate is deleted before the next db_id starts, and the run aborts if `data/oracle` exceeds 4 GB.

Seeds: the global seed is 0. Candidate i of db d uses `random.seed(crc32("0|d|i"))`. Neighbor generation for gold g uses `np.random.seed(crc32("0|d|g"))` and `random.seed(...)` from the same string.

Command: `PYTHONHASHSEED=0 oracle/.venv/bin/python oracle/build_suite.py`. The `--dbs a b` option rebuilds selected dbs and updates the manifest in place.

### Candidate caps and disk use

- **40 candidates per db_id.** wta_1 used **15**, because its original is 100 MB and its neighbor generation and candidate writing make transient copies of it; its parallel workers were also capped at 4. car_1 (65 KB) and world_1 (320 KB) are small, so they first ran with 15 and were then rebuilt with 40. world_1's undistinguished neighbors fell from 294 to 42.
- Table sizes are bounded by the authors' fuzzer itself: at most 2,500 rows per table, and most tables have about 30 to 230 rows. Every candidate stayed under 20 MB after VACUUM, so no further row cap was needed.
- Peak `data/oracle` during the capped run was about 104 MB, measured after each db. The final size is **104 MB**, of which 100 MB is the copied wta_1 original. Each suite without its original is 0.1 to 0.7 MB.
- Runtime: the full build took 25 s wall time (10 cores), and the car_1/world_1 rebuild took about 4 s.

### Result

- 109 suite files in total, original included.
- Suite size per db: battle_death 5, car_1 6, concert_singer 5, course_teach 4, cre_Doc_Template_Mgt 5, dog_kennels 6, employee_hire_evaluation 4, flight_2 12, museum_visit 5, network_1 3, orchestra 5, pets_1 5, poker_player 8, real_estate_properties 2, singer 4, student_transcripts_tracking 7, tvshow 5, voter_1 4, world_1 9, wta_1 5.
- Distillation: 29,693 neighbors in total and 166 left undistinguished (0.56%). For 351 of the 379 golds every neighbor was distinguished. Some of the leftover neighbors are true equivalents that no database can separate.

## Sanity checks (`oracle/.venv/bin/python oracle/sanity.py`, about 5 s)

- **(a) Gold matches itself:** 719/719 True, 0 False, 0 None, so there are 0 failures.
- **(b) 50 wrong variants of devA golds:** the variants were made by rules and reviewed by hand; all 50 are semantically non-equivalent. Rules and counts:
  - 9 drop a WHERE/AND predicate
  - 9 flip a comparison (`>` to `>=` and similar)
  - 9 replace `COUNT(*)` with `COUNT(DISTINCT non-pk column)`
  - 9 swap an aggregate (min/max, avg/sum)
  - 7 drop a DISTINCT
  - 5 flip the sort order
  - 2 change AND to OR

  **The oracle rejects 50/50 (100%).** For comparison, plain execution match on the original Spider DB alone rejects only 42/50. The 8 it misses are 4 flipped comparisons (museum_visit), 3 COUNT DISTINCT variants (2 on car_1, 1 on museum_visit) and 1 dropped predicate (pets_1).
- **(c) Informativeness:** 377/379 unique golds (716/719 questions) give a different denotation on at least two suite databases. The two that do not:
  - `SELECT LOCATION, name FROM stadium WHERE capacity BETWEEN 5000 AND 10000` (concert_singer): see the BETWEEN limitation below.
  - `SELECT name FROM city WHERE Population BETWEEN 160000 AND 90000` (world_1): this is empty on every database by construction.
- **Speed:** 0.006 s per pair on average for gold/gold over a 2 to 12 file suite. Wrong predictions usually stop at the first database that disagrees (about 0.001 s).

## Known limitations and differences from the official suite

- **Not the official suite.** It uses different random draws, and its suites are much smaller. The official suite sampled up to about 1,000 databases per gold query, using that query's own constants, and distilled over all 1,034 dev queries. Here each db shares a pool of 40 candidates (15 for wta_1), with constants from all dev golds of that db, and distillation covers only the 379 unique devA/devB golds. The paper's guarantee (every neighbor distinguished) holds for 351 of the 379 golds. Expect the oracle to be somewhat more permissive than the official suite, meaning more false "equivalent" verdicts on rare corner cases.
- **Upstream BETWEEN bug, not patched.** It is not a Python 3.11 issue, so it was left alone and recorded here. `sql_util/parse.py` line 233 uses the regex `(?:not )between`, which makes `NOT` mandatory, so constants from a plain `BETWEEN a AND b` are never fed to the fuzzer. Golds that use BETWEEN get fewer boundary-probing rows; the concert_singer case above is the visible symptom. To fix it, change the group to `(?:not )?`. That change would have to be listed as a patch and the suites rebuilt.
- **Test bias.** The 50 variants come mostly from pets_1, car_1, museum_visit and wta_1 (devA file order), and they are coarse edits. A 100% rejection rate shows the suite is not degenerate; it is not an estimate of the false-positive rate on real model outputs.
- **Timeouts.** A prediction that runs longer than 10 s on any suite database is judged False, which follows the official intent that a timeout counts as an exception.
- **Value literals.** `plug_value=False`, so the prediction must contain the right literals.
- **Evaluator quirks.** The official evaluator's own quirks apply: bag semantics, `order by` detected by substring, and float equality is exact.
