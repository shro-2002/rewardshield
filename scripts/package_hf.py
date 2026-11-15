"""Stage Hugging Face model and dataset repos locally. Uploading is a separate, explicit step.

uv run python scripts/package_hf.py --out hf_stage            # stage only, prints a manifest
uv run python scripts/package_hf.py --out hf_stage --upload --user shro-2002   # after the owner approves

Licences (checked 2026-11-15): adapters are derivatives of Tiny Aya Global (CC BY-NC 4.0 with Cohere's
acceptable-use addendum). Datasets are split by origin into three repos, each with its own card (reports/hf_cards/):
Spider-derived data (CC BY-SA 4.0), model-generated trajectories (mixed, documented per component), and our
verdicts/labels/metrics (CC BY-SA 4.0, as they quote Spider content). Not staged: Spider databases (download from the source), the rebuilt oracle
databases (TestSuiteEval has no licence), generated candidate databases (regenerable), optimizer states.
"""

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_FILES = ["adapter_config.json", "adapter_model.safetensors", "tokenizer.json", "tokenizer_config.json",
                 "chat_template.jinja", "train_summary.json"]
ADAPTERS = {
    "E01": ("runs/E01_sft/E01_adapter", "gold-trajectory warm start, 150 steps x 16 (loss also on tool results)"),
    "E04": ("runs/E04/out/E04_adapter", "E01 + 100 steps x 16 on 911 single-1-accepted self-generated samples"),
    "E05": ("runs/E04/out/E05_adapter", "E01 + 100 steps x 16 on 911 targeted-4-accepted self-generated samples"),
    "E07": ("runs/E07/out/E07_adapter", "E01 + 100 steps x 16 on gold trajectories for a matched 911-question set"),
}
DATASETS = {
    # Spider-derived only: questions, schemas, gold SQL, rows of the Spider databases, templated replies we wrote.
    "rewardshield-spider-splits": ("cc-by-sa-4.0", {
        "splits": ["data/splits/devA.jsonl", "data/splits/devB.jsonl", "data/splits/train.jsonl",
                   "data/splits/train_pool.jsonl", "data/splits/train_pool_1200.jsonl", "data/splits/summary.json",
                   "data/splits/e02_rerun_long.jsonl"],
        "gold_trajectories": ["runs/E01/sft_gold.jsonl", "runs/E01/sft_gold_summary.json",
                              "runs/E07/sft_gold_matched.jsonl", "runs/E07/e07_summary.json"],
    }),
    # Model-generated text (Tiny Aya Global and its adapters) embedded in Spider prompts: mixed origin.
    "rewardshield-trajectories": ("other", {
        "pools": ["runs/E02/pool_devA.jsonl", "runs/E02/pool_train.jsonl"],
        "sft_arms": ["runs/E04/sft_single-1.jsonl", "runs/E04/sft_targeted-4.jsonl", "runs/E04/arms_summary.json"],
        "eval_trajectories": [f"runs/E04/out/{m}_{s}{x}.jsonl" for m, s in
                              [("E00", "devA"), ("E00", "devB"), ("E01", "devA"), ("E01", "devB"), ("E04", "devB"), ("E05", "devB")]
                              for x in ("", "_oracle")] + ["runs/E07/out/E07_devB.jsonl", "runs/E07/out/E07_devB_oracle.jsonl"],
        "latency": [f"runs/E07/out/lat_{m}.jsonl" for m in ("E00", "E01", "E04", "E05", "E07")],
        "exploratory": ["runs/exploratory/union_oracle", "runs/exploratory/flight2"],
    }),
    # Our verdicts, labels, metrics and logs (keyed by question id; label reasons quote short SQL fragments).
    "rewardshield-verification": ("cc-by-sa-4.0", {
        "verdicts": ["runs/E03/verdicts_devA.jsonl", "runs/E03/verdicts_train.jsonl", "runs/E03/oracle_devA.jsonl",
                     "runs/E03/analysis_verifiers.json"],
        "llm_labels": ["runs/E03/labels_devA.jsonl", "runs/E03/labels_train.jsonl"],
        "analysis": ["runs/E04/analysis_E01toE04.json", "runs/E04/analysis_E01toE05.json", "runs/E04/analysis_H3.json",
                     "runs/E04/analysis_E00toE05.json", "runs/E07/analysis_E07.json", "runs/bench_devA/summary.json",
                     "reports/toolkit_metrics.json", "reports/toolkit_metrics.md", "runs/repro_check/report.json"],
        "exploratory": [f"runs/exploratory/audit{i}.out" for i in range(1, 6)] + ["runs/exploratory/reconcile_devB_rates.out"],
        "logs": ["runs/E04/out/rewardshield-e04-arms.log", "runs/E04/out/E04_train.log", "runs/E04/out/E05_train.log",
                 "runs/E04/summaries", "runs/E01_sft/rewardshield-e01-sft.log", "runs/E07/out/rewardshield-e07-control.log",
                 "runs/E07/out/E07_train_summary.json"],
        "configs": ["kaggle/cmds"],
    }),
}


def model_card(name: str, desc: str) -> str:
    return f"""---
base_model: CohereLabs/tiny-aya-global
library_name: peft
license: cc-by-nc-4.0
tags: [text-to-sql, agent, lora, rewardshield, lexsi-hackathon]
---
# RewardShield {name} LoRA adapter for Tiny Aya Global

{desc}. LoRA r16 (alpha 32, dropout 0.05, all attention and MLP projections), trained with TRL `SFTTrainer`
(supervised fine-tuning, not reinforcement learning). Prompt and tool format: AgentTune's Tiny Aya fallback
tool prompt with one `run_sql` tool. Results, intervals and caveats: see the GitHub repo RESULTS.md.

Licence: CC BY-NC 4.0, inherited from the base model; use is also subject to the Cohere Labs acceptable-use
policy. Research artefact from the Lexsi AI Safety and Alignment Hackathon (Track 3); not for production.
"""


def stage(out: Path) -> dict:
    manifest = {"models": {}, "dataset": [], "missing": []}
    for name, (src, desc) in ADAPTERS.items():
        src_dir = ROOT / src
        if not (src_dir / "adapter_config.json").exists():
            manifest["missing"].append(src)
            continue
        dst = out / "models" / f"rewardshield-{name.lower()}-adapter"
        dst.mkdir(parents=True, exist_ok=True)
        for f in ADAPTER_FILES:
            if (src_dir / f).exists():
                shutil.copy2(src_dir / f, dst / f)
        (dst / "README.md").write_text(model_card(name, desc))
        manifest["models"][name] = str(dst)
    for repo, (_, groups) in DATASETS.items():
        ds = out / "datasets" / repo
        for group, paths in groups.items():
            for rel in paths:
                src = ROOT / rel
                if not src.exists():
                    manifest["missing"].append(rel)
                    continue
                dst = ds / group / Path(rel).name
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir():
                    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.sqlite"))
                else:
                    shutil.copy2(src, dst)
                manifest["dataset"].append(f"{repo}/{group}/{Path(rel).name}")
        card = ROOT / "reports" / "hf_cards" / f"{repo}.md"
        if card.exists():
            shutil.copy2(card, ds / "README.md")
        else:
            manifest["missing"].append(str(card.relative_to(ROOT)))
    return manifest


def upload(out: Path, user: str) -> None:
    from huggingface_hub import HfApi

    api = HfApi()
    models = api.create_collection("RewardShield models", namespace=user, private=False, exists_ok=True,
                                   description="LoRA adapters for Tiny Aya Global (Lexsi hackathon, Track 3)")
    for d in sorted((out / "models").iterdir()):
        repo = f"{user}/{d.name}"
        api.create_repo(repo, repo_type="model", private=False, exist_ok=True)
        api.upload_folder(folder_path=str(d), repo_id=repo, repo_type="model")
        api.add_collection_item(models.slug, repo, "model", exists_ok=True)
    data = api.create_collection("RewardShield data", namespace=user, private=False, exists_ok=True,
                                 description="Splits, trajectories, verdicts, labels, metrics, logs (separately licensed repos)")
    for d in sorted((out / "datasets").iterdir()):
        repo = f"{user}/{d.name}"
        api.create_repo(repo, repo_type="dataset", private=False, exist_ok=True)
        api.upload_folder(folder_path=str(d), repo_id=repo, repo_type="dataset")
        api.add_collection_item(data.slug, repo, "dataset", exists_ok=True)
    print("collections:", models.url, data.url)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="hf_stage")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--user")
    args = ap.parse_args()
    out = ROOT / args.out
    manifest = stage(out)
    print(json.dumps(manifest, indent=1))
    if args.upload:
        if not args.user:
            raise SystemExit("--upload needs --user")
        upload(out, args.user)


if __name__ == "__main__":
    main()
