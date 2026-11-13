# Decision log

Append-only. Newest last. Times in IST.

- **2026-11-14 01:40** Research direction approved by the user: RewardShield, Track 3, Tiny Aya Global, AgentTune + AuditKIT.
- **01:44** Environment: Python 3.12, `agenttune==1.1.5` (pins torch 2.11.0, trl 1.7.1, transformers ≥5.15,<6), `auditkit[jsonschema]==1.1.11`, sqlglot; locked in `uv.lock`. Resolved transformers 5.23.0, peft 0.21.3, bitsandbytes 0.50.2.
- **01:45** Model source: Kaggle Models `cohere-labs/tiny-aya/transformers/global/1` (CC BY-NC 4.0). Same checkpoint family as the gated HF repo; avoids needing an HF token on Kaggle kernels. HF login still needed to publish artifacts.
- **01:46** Spider 1.0 (train, dev, 166 databases) from Kaggle mirror `jeromeblanchet/yale-universitys-spider-10-nlp-dataset` (original licence CC BY-SA 4.0).
- **01:47** Official test-suite databases: Google Drive download blocked by quota; searching for a public mirror. Fallback oracle if none: ParSEval (independent tool, Apache-2.0) plus hand labels, declared as a deviation.
- **01:52** Oracle coverage fix (before any sampling): the official test suite exists only for dev databases. Dev databases split by db_id into dev-A (oracle-labelled verifier audit pool, verifier tuning allowed) and dev-B (final held-out model eval). H1/H2 measured on dev-A; H3 on dev-B. Training pool stays on train databases. Recorded in HYPOTHESES.md (draft v1).
- **01:52** Random-k draws its extra databases from the same candidate set as targeted-k, so H2 isolates the selection rule from the generator.
- **01:56** Kaggle GPU blocked: weekly 30 h quota already used on this account. Mac MLX measured at 12.3 tok/s generation (short run); too slow for the full pool. GPU decision escalated to the user (HF credits or quota reset).
- **01:57** Evaluated answer = last successfully executed SQL in the trajectory (Tiny Aya answers in prose after the tool call); same convention as AgentTune `result_match_reward`.
- **02:00** targeted-k fills slots left after greedy mutant killing with informative candidates (gold returns non-NULL rows), seeded, so it spends the same database budget as random-k.
- **02:04** Security: model SQL is untrusted. Added SQLite length limits (1 MB value, 100 KB statement) and a 20 MB result cap on top of the time limit and read-only authorizer.
