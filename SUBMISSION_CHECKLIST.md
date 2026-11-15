# Round 1 submission checklist

Deadline: **Nov 15 2026, 11:59 PM AoE = Nov 16, 5:29 PM IST.** Target: submitted by Nov 16, 12:00 IST.
Source: https://hackathon.lexsi.ai/submit and /tracks (re-read 2026-11-15 09:50 IST; template unchanged).
Legend: [x] done with evidence · [~] drafted, waiting on a named item · [ ] not done.

## Form inputs
- [x] Registered email (owner confirmed, DECISIONS.md 2026-11-14 20:52)
- [~] Abstract under 500 words: WRITEUP.md "Abstract" (389 words); E07 sentence pending
- [~] HF model collection, public, un-gated: staged by `scripts/package_hf.py` (E01, E04, E05; E07 after the job); **upload needs owner approval**
- [~] HF dataset collection, public: staged by `scripts/package_hf.py`, card `reports/hf_dataset_card.md`; **licence choice and upload need owner approval**
- [~] Write-up: WRITEUP.md (every * section present); placeholders marked ⟨PENDING⟩
- [~] GitHub repo with reproducibility notes: README.md, LICENSE (MIT), history scanned for secrets (clean); **no remote yet, creation needs owner approval**
- [x] Repos and models used, track, problem statements: WRITEUP.md (Track 3; statements 9 and 6)

## Rules
- [x] Track 3 toolkits used together: AgentTune reward callable in AgentTune's rollout path + AuditKIT `agent_eval` on all evaluation episodes (`reports/upstream/INTEGRATION_NOTES.md`, tests)
- [x] Core model from permitted list: Tiny Aya Global
- [x] More than one before/after metric: task success, clean-episode rate, call execution rate, commit rate, correct-given-committed, latency (`reports/toolkit_metrics.md`)
- [ ] Project deployed publicly by the deadline (HF + GitHub after approval)
- [ ] Optional: ROI comparison (only after the required items)

## Required write-up sections (* on the template), all present in WRITEUP.md
- [x] Title + one-line claim · [x] Tracks + problem statements · [~] Abstract · [~] Headline before → after (E07 column pending)
- [x] Base model + method · [x] Problem statement, why this problem · [x] Repos used, per-kit usage, how they connect
- [x] Models and licences · [x] Datasets, licences, splits, leak check · [x] Tool environments, trajectories [T3]
- [~] Metrics incl. task success, tool-call accuracy, latency [T3] (batch-1 latency pending E07 job)
- [x] Method / hyperparameters · [~] Results tables (E07 pending) · [x] Limitations · [x] With more credits (plan + forecast)
- [~] Artifacts (URLs after publishing) · [x] Documentation and reproduction · [x] Declaration · [x] Teammates (solo)

## Integrity items
- [x] Pre-registered results preserved; corrections dated inline; exploratory analyses separated (RESULTS.md E-1 to E-8)
- [x] Audit reproduced (`runs/exploratory/audit*.out`); one audit count not reproduced and stated (258 vs 379)
- [x] Deviations recorded: unapplied exclusion (3 dev-B questions), generator defects, agenttune column meaning
- [~] Blind human labels: `runs/exploratory/blind_labels/to_label.csv` (60 rows) **for the owner**; scorer ready
- [x] Fresh reproducibility check: `scripts/repro_check.py` (13/13 pass, 2026-11-15 10:15); final run after E07
