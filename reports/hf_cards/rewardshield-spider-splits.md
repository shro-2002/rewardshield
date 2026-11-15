---
license: cc-by-sa-4.0
task_categories: [text-generation]
tags: [text-to-sql, spider, lexsi-hackathon, rewardshield]
pretty_name: RewardShield Spider splits and gold trajectories
---
# RewardShield: Spider splits and gold trajectories

Schema-disjoint splits of Spider 1.0 (easy and medium questions) and the gold-SQL agent trajectories used to
warm-start and control the RewardShield experiments (Lexsi AI Safety and Alignment Hackathon, Track 3).
Code, results and caveats: https://github.com/shro-2002/rewardshield

| Folder | Contents |
|---|---|
| `splits/` | train (5,864 questions, 146 databases), its warm-start/pool partition (`train_pool.jsonl`), the 1,200-question pool, dev-A (340 / 10 databases), dev-B (379 / 10 databases); seed 20261114 |
| `gold_trajectories/` | E01 warm-start set (1,500) and E07 control set (911): system prompt with schema, question, one `run_sql` call with the gold SQL, its real result rows from the Spider database, a templated reply |

**Licence: CC BY-SA 4.0.** Everything here is derived from Spider 1.0 (Yu et al., 2018; CC BY-SA 4.0) plus
formatting and templated text written by us, released under the same licence. Attribution: Tao Yu et al.,
"Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task", EMNLP 2018.

**Not included, and how to regenerate.** Spider databases: download Spider 1.0 from its authors or the Kaggle
mirror `jeromeblanchet/yale-universitys-spider-10-nlp-dataset`, then `uv run python scripts/build_splits.py`
reproduces these splits byte for byte. Field `db_path` is a relative path into that download.

**Known issues.** flight_2 (dev-B) stores whitespace-padded codes, so 34 of its gold queries return empty sets or
zero counts on the original database; see the GitHub RESULTS.md section E-6. Six question strings recur across
splits on different databases (listed in the README, leak check).
