CMD = 'set -ex; python scripts/train_sft.py --model $MODEL --data runs/E01/sft_gold.jsonl --out /kaggle/working/E01_adapter --max-steps 150 --seed 0 && python scripts/run_rollouts.py --model $MODEL --adapter /kaggle/working/E01_adapter --split data/splits/devA.jsonl --spider-root $SPIDER --out /kaggle/working/E01_devA.jsonl && python scripts/run_rollouts.py --model $MODEL --adapter /kaggle/working/E01_adapter --split data/splits/devB.jsonl --spider-root $SPIDER --out /kaggle/working/E01_devB.jsonl'
import glob, os, subprocess, sys
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
