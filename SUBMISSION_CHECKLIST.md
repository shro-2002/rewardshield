# Round 1 submission checklist (final)

**Resubmitted with the corrected abstract and one-line claim (AgentTune 1.1.7 outcome): 2026-11-16, 09:08 IST. This replaces the first submission.** First submission: 2026-11-15, 12:28 IST (Track 3; problem statements: reward design and reward-hacking defences, data and database agents; repos AgentTune + AuditKIT; model Tiny Aya Global). Only the latest submission counts, so a resubmission before the deadline replaces it.

Deadline: Nov 15 2026, 11:59 PM AoE = Nov 16, 5:29 PM IST. Target: submitted by Nov 16, 12:00 IST.
Template re-read on https://hackathon.lexsi.ai/submit and /tracks on 2026-11-15 09:50 IST (unchanged).
Paste-ready form fields: `SUBMISSION_PACKAGE.md`.

## Form inputs

| Item | Status | Evidence |
|---|---|---|
| Registered email | done (owner) | DECISIONS.md 2026-11-14 20:52 |
| Abstract under 500 words | done | README.md "Abstract", 392 words |
| HF model collection, public, un-gated | done | https://huggingface.co/collections/shro-2002/rewardshield-models (4 adapters; API: private=false, gated=false; anonymous load + generate of E05 verified) |
| HF dataset collection, public | done | https://huggingface.co/collections/shro-2002/rewardshield-data (3 repos, separately licensed; API: private=false, gated=false) |
| Write-up (GitHub README) | done | https://github.com/shro-2002/rewardshield (README.md; no placeholders) |
| GitHub repo with reproducibility notes | done | README "Repository guide"; fresh clone + anonymous HF fetch + `repro_check.py`: 14/14 pass |
| Repos and models used, track, problem statements | done | README: Track 3; problem statements 9 and 6; AgentTune, AuditKIT, Tiny Aya Global |

## Rules

| Item | Status | Evidence |
|---|---|---|
| Track 3 kits used together | done | AgentTune reward callable in `create_rollout_fn` + `combine_rewards` paths (`tests/test_agenttune_reward.py`); AuditKIT `agent_eval` on all evaluation episodes (`scripts/auditkit_eval.py`, `reports/toolkit_metrics.md`) |
| Core model from permitted list | done | Tiny Aya Global |
| More than one before/after metric | done | task success, clean tool-call episodes, call execution rate, commit rate, correct-given-committed, batch-1 latency |
| Deployed publicly by the deadline | done | links above verified anonymously (HTTP 200) |
| Optional ROI comparison | not done | skipped by decision: required items first |

## Required write-up sections (all in README.md)

Title + one-line claim; tracks + problem statements; abstract; headline before → after; base model + method; problem statement, approach, why this problem; repos used, per kit, how they connect; models and licences; datasets, licences, splits, leak check; tool environments and trajectories [T3]; metrics incl. task success, tool-call accuracy, latency [T3]; method and hyperparameters; results (before/after, E07 controls and confounds, CIs, negative results, samples, compute); limitations; with more credits (plan + forecast); artifacts; documentation and reproduction; declaration; teammates; LLM usage statement. Check: `grep -c PENDING README.md` = 0.

## Integrity and quality checks

| Check | Result | Evidence |
|---|---|---|
| Test suite | 57 passed | `uv run pytest -q` (local and fresh clone) |
| Fresh-clone reproducibility | 14/14 PASS | clone of github.com/shro-2002/rewardshield, `uv sync`, `fetch_artifacts.py` (anonymous), `repro_check.py` |
| Exploratory reproduction | 16/16 PASS incl. seed-averaged H2 (dev-A −0.25, dev-B −1.57) | `repro_check.py --with-exploratory` (local), `runs/repro_check/report.json` |
| Pre-registered results preserved | done | RESULTS.md E00-E05 unchanged, dated corrections inline; exploratory E-1 to E-9 separate |
| Audit reconciliation | done | RESULTS.md E-9: 18.1% vs 12.1% (population definitions), 258 vs 379 (definitions; both reproduced) |
| E07 interpretation | done | RESULTS.md E07 and README: what it controls, what it does not, no causal claim about verification |
| Secrets / personal data | clean | history scan (0 token patterns); staged HF files scanned; no owner email; blind-label key not published |
| Licences | done | code MIT; adapters CC BY-NC 4.0 + Cohere AUP; Spider-derived data CC BY-SA 4.0; trajectories per-component card; oracle and generated DBs not redistributed, regeneration documented |
| Upstream contribution | filed | https://github.com/Lexsi-Labs/AgentTune/issues/20, https://github.com/Lexsi-Labs/AgentTune/pull/21 (no duplicates found; patch tests pass; upstream failures identical before/after) |
| GPU policy | done | only E07 + latency run; E06, E08, E09, E10 not run |

## Open items for the owner

- ~~Submit the form~~ done 2026-11-15 12:28 IST. HF community articles return 403 for this account, so the GitHub README serves as the write-up.
- Post `reports/organizer_question.md` in the hackathon Discord (#hackathon-lexsi); the connector was unavailable from this session.
- Optional: label `runs/exploratory/blind_labels/to_label.csv`, then `uv run python scripts/exploratory/score_blind_labels.py` (no κ is claimed until then).
