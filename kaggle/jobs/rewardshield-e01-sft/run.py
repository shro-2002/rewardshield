CMD = 'set -x; nproc_gpu=$(nvidia-smi -L | wc -l); A=/kaggle/working/E01_adapter\nif [ "$nproc_gpu" -ge 2 ]; then torchrun --nproc_per_node 2 scripts/train_sft.py --model $MODEL --data runs/E01/sft_gold.jsonl --out $A --max-steps 150 --grad-accum 8 --seed 0 || { rm -rf $A; CUDA_VISIBLE_DEVICES=0 python scripts/train_sft.py --model $MODEL --data runs/E01/sft_gold.jsonl --out $A --max-steps 150 --grad-accum 16 --seed 0; }; else python scripts/train_sft.py --model $MODEL --data runs/E01/sft_gold.jsonl --out $A --max-steps 150 --grad-accum 16 --seed 0; fi\ntest -f $A/adapter_config.json || exit 1\nCUDA_VISIBLE_DEVICES=0 python scripts/run_rollouts.py --model $MODEL --adapter $A --split data/splits/devA.jsonl --spider-root $SPIDER --out /kaggle/working/E01_devA.jsonl > /kaggle/working/evalA.log 2>&1 &\nCUDA_VISIBLE_DEVICES=1 python scripts/run_rollouts.py --model $MODEL --adapter $A --split data/splits/devB.jsonl --spider-root $SPIDER --out /kaggle/working/E01_devB.jsonl > /kaggle/working/evalB.log 2>&1 &\nwait; tail -3 /kaggle/working/evalA.log /kaggle/working/evalB.log'
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
