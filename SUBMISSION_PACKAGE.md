# Submission package (paste into https://hackathon.lexsi.ai/submit)

**Email:** the registered email (owner fills in).

**Title:** RewardShield: how reliable are execution rewards for a small database agent, and does it matter?

**One-line claim:** in a pre-registered, controlled study on Tiny Aya Global, checking SQL rewards on a few extra mutation-guided databases removes a small but replicated share of false accepts at equal cost; filtering self-generated training data with the better verifier did not measurably change the fine-tuned agent; and AgentTune's shipped SQL reward scores every Tiny Aya rollout −1, which we reproduce and patch.

**Abstract (392 words):**

Execution rewards for SQL agents usually run the predicted and gold queries on one database and compare the rows. A wrong query that happens to return the same rows is rewarded, and a model trained on such rewards may learn it. We ran a controlled investigation of this for a small database agent: how often it happens, what catching it costs, which failure modes dominate, and whether better verification changes what the agent learns.

The agent is Tiny Aya Global (3B) answering Spider questions with one `run_sql` tool in AgentTune's format. Five verifiers were compared on 1,360 sampled trajectories, labelled by an independent test-suite oracle rebuilt with Zhong et al.'s own generator: single-database match (single-1), AgentTune's shipped `result_match_reward`, 4 random databases, 4 databases chosen to kill mutants of the gold query (targeted-4), and 16 random databases. Hypotheses, sample sizes and decision rules were registered before sampling.

On the dev-A audit pool, targeted-4 lowers the false-accept share from 3.88% (single-1) to 1.39% and beats random-4 at equal cost (H1, H2 supported). An independent audit showed the H2 size depended on one random draw of databases: averaged over 200 draws the gap is −0.25 points [−0.59, −0.00] on dev-A and −1.57 [−2.67, −0.60] on held-out dev-B outputs. On dev-B, false accepts are far more common, and most come from one schema (flight_2) whose whitespace-padded codes make gold results empty, a blind spot for every verifier.

Downstream, two LoRA SFT arms trained from the same warm start on 911 single-1-accepted or targeted-4-accepted self-generated samples reach 63.1% and 62.0% held-out test-suite accuracy (H3 inconclusive: −1.06 points [−4.22, +1.85]; minimum detectable effect about 4.3 points). A matched gold-trajectory control reaches 59.4%, no better than the 59.6% warm start, so the arms' gain is not explained by the extra training steps; it came through committing a query more often, not through better queries, and it is confounded with the source of the training data, so it does not isolate verification.

The toolkit contribution: RewardShield's verifiers run as a reward callable inside AgentTune's own rollout scoring, all evaluation episodes are scored through AuditKIT's agent evaluation (task success 51.5% → 63.1%, clean tool-call episodes 80.2% → 90.0%, batch-1 latency 5.7 → 4.9 s), and we found, reproduced and patched a defect that makes AgentTune's shipped SQL reward return −1 for every rollout under tool-blind chat templates such as Tiny Aya's.

**Hugging Face model collection:** https://huggingface.co/collections/shro-2002/rewardshield-models

**Hugging Face dataset collection:** https://huggingface.co/collections/shro-2002/rewardshield-data

**Write-up (GitHub README):** https://github.com/shro-2002/rewardshield

**GitHub repo:** https://github.com/shro-2002/rewardshield

**Repos and models used:** AgentTune 1.1.5 (Lexsi Labs), AuditKIT 1.1.11 (Lexsi Labs), Tiny Aya Global (Cohere Labs, CC BY-NC 4.0); TRL for LoRA SFT; Spider 1.0 (CC BY-SA 4.0); Zhong et al. test-suite evaluation (Apache-2.0) and TestSuiteEval generator (used, not redistributed).

**Track:** Track 3, Agentic fine-tuning.

**Problem statements:** 9. Reward design and reward-hacking defences; 6. Data and database agents.

**Upstream contribution:** https://github.com/Lexsi-Labs/AgentTune/issues/20 and https://github.com/Lexsi-Labs/AgentTune/pull/21
