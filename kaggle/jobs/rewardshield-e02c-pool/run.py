CMD = 'set -x; A=$(dirname $(find /kaggle/input -name adapter_config.json -path "*adapter*" | head -1)); test -f $A/adapter_config.json || exit 1\nR="python scripts/run_rollouts.py --model $MODEL --adapter $A --spider-root $SPIDER --n 4 --temperature 0.8 --seed 0"\nCUDA_VISIBLE_DEVICES=0 $R --split data/splits/devA.jsonl --out /kaggle/working/E02_pool_devA.jsonl > /kaggle/working/g0.log 2>&1 &\nCUDA_VISIBLE_DEVICES=1 $R --split data/splits/train_pool_1200.jsonl --offset 943 --limit 257 --out /kaggle/working/E02_pool_train_c.jsonl > /kaggle/working/g1.log 2>&1 &\nwait; for f in /kaggle/working/g*.log; do tail -n 2 $f; done; wc -l /kaggle/working/E02_*.jsonl'
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
