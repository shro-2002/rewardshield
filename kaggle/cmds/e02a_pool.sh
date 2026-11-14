set -x; A=$(dirname $(find /kaggle/input -name adapter_config.json -path "*adapter*" | head -1)); test -f $A/adapter_config.json || exit 1
R="python scripts/run_rollouts.py --model $MODEL --adapter $A --spider-root $SPIDER --n 4 --temperature 0.8 --seed 0"
CUDA_VISIBLE_DEVICES=0 $R --split data/splits/train_pool_1200.jsonl --offset 0 --limit 472 --out /kaggle/working/E02_pool_train_a.jsonl > /kaggle/working/g0.log 2>&1 &
CUDA_VISIBLE_DEVICES=1 $R --split data/splits/train_pool_1200.jsonl --offset 472 --limit 471 --out /kaggle/working/E02_pool_train_b.jsonl > /kaggle/working/g1.log 2>&1 &
wait; for f in /kaggle/working/g*.log; do tail -n 2 $f; done; wc -l /kaggle/working/E02_*.jsonl
