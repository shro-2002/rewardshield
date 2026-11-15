"""Sync code to a private Kaggle dataset and push a GPU job that runs one command.

uv run python scripts/kaggle_job.py sync                       # upload src/, scripts/, data/splits, SFT data
uv run python scripts/kaggle_job.py push E01-train "python scripts/train_sft.py ..." [--after E00-base]
Inside the job: MODEL, SPIDER and CODE are environment variables; outputs go to /kaggle/working/.
"""

import argparse
import time
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
USER = "sonika20000002"
CODE_DATASET = f"{USER}/rewardshield-code"
SPIDER_DATASET = "jeromeblanchet/yale-universitys-spider-10-nlp-dataset"
MODEL_SOURCE = "cohere-labs/tiny-aya/transformers/global/1"
STAGE = ROOT / "kaggle" / "_stage"
SYNC_PATHS = ["src", "scripts", "data/splits", "third_party/test-suite-sql-eval", "runs/E01/sft_gold.jsonl", "runs/E04/sft_single-1.jsonl",
              "runs/E04/sft_targeted-4.jsonl", "runs/E07/sft_gold_matched.jsonl", "pyproject.toml"]

VERSION_SETTLE_S = 90
BOOT = '''import glob, os, subprocess, sys
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "agenttune==1.1.5", "auditkit==1.1.11", "sqlglot", "sqlparse", "nltk"], check=True)
code = glob.glob("/kaggle/input/**/rewardshield-code*/src", recursive=True) or glob.glob("/kaggle/input/**/src/rewardshield", recursive=True)
CODE = os.path.dirname(code[0]) if code[0].endswith("src") else os.path.dirname(os.path.dirname(code[0]))
MODEL = os.path.dirname([p for p in glob.glob("/kaggle/input/**/config.json", recursive=True) if "global" in p][0])
SPIDER = os.path.dirname(glob.glob("/kaggle/input/**/spider/tables.json", recursive=True)[0])
env = {**os.environ, "MODEL": MODEL, "SPIDER": SPIDER, "CODE": CODE, "PYTHONPATH": CODE + "/src"}
print("CODE", CODE, "MODEL", MODEL, "SPIDER", SPIDER, flush=True)
subprocess.run("nvidia-smi --query-gpu=name,memory.total --format=csv", shell=True)
os.chdir(CODE)
rc = subprocess.run(CMD, shell=True, env=env).returncode
sys.exit(rc)
'''


def run(cmd: list[str]) -> str:
    out = subprocess.run(cmd, capture_output=True, text=True)
    text = "\n".join(l for l in (out.stdout + out.stderr).splitlines() if "outdated" not in l)
    print(text.strip()[-600:])
    return text


def sync() -> None:
    shutil.rmtree(STAGE, ignore_errors=True)
    dst = STAGE / "rewardshield-code"
    for rel in SYNC_PATHS:
        src = ROOT / rel
        if not src.exists():  # e.g. runs/E04 before the arm sets are built
            continue
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        else:
            shutil.copy2(src, target)
    (dst / "dataset-metadata.json").write_text(json.dumps(
        {"title": "rewardshield-code", "id": CODE_DATASET, "licenses": [{"name": "other"}]}))
    exists = "403" not in run(["kaggle", "datasets", "status", CODE_DATASET]) and "404" not in run(
        ["kaggle", "datasets", "status", CODE_DATASET])
    if exists:
        run(["kaggle", "datasets", "version", "-p", str(dst), "-m", "sync", "-r", "zip", "-q"])
    else:
        run(["kaggle", "datasets", "create", "-p", str(dst), "-r", "zip", "-q"])
    # ponytail: fixed wait, status reports "ready" for the previous version until the new one lands
    time.sleep(VERSION_SETTLE_S)
    while "ready" not in run(["kaggle", "datasets", "status", CODE_DATASET]):
        time.sleep(15)


def push(name: str, cmd: str, after: list[str], datasets: list[str], shape: str) -> None:
    slug = f"rewardshield-{name.lower()}"
    kdir = ROOT / "kaggle" / "jobs" / slug
    kdir.mkdir(parents=True, exist_ok=True)
    (kdir / "run.py").write_text(f"CMD = {cmd!r}\n" + BOOT)
    (kdir / "kernel-metadata.json").write_text(json.dumps({
        "id": f"{USER}/{slug}", "title": slug, "code_file": "run.py", "language": "python", "kernel_type": "script",
        "is_private": True, "enable_gpu": True, "enable_internet": True, "machine_shape": shape,
        "dataset_sources": [CODE_DATASET, SPIDER_DATASET, *datasets], "model_sources": [MODEL_SOURCE],
        "kernel_sources": [f"{USER}/rewardshield-{a.lower()}" for a in after], "competition_sources": []}, indent=2))
    run(["kaggle", "kernels", "push", "-p", str(kdir)])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["sync", "push"])
    ap.add_argument("name", nargs="?")
    ap.add_argument("cmd", nargs="?")
    ap.add_argument("--after", nargs="*", default=[])
    ap.add_argument("--datasets", nargs="*", default=[], help="extra datasets, e.g. an adapter from a kernel that ended in ERROR")
    ap.add_argument("--shape", default="NvidiaTeslaT4", choices=["NvidiaTeslaT4", "NvidiaTeslaP100"],
                    help="NvidiaTeslaT4 is 2x T4; NvidiaTeslaP100 is one P100 (separate queue)")
    args = ap.parse_args()
    if args.action == "sync":
        sync()
    else:
        if not (args.name and args.cmd):
            sys.exit("push needs NAME and CMD")
        push(args.name, args.cmd, args.after, args.datasets, args.shape)


if __name__ == "__main__":
    main()
