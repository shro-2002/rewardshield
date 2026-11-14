set -x; A0=$(dirname $(find /kaggle/input -name adapter_config.json -path "*adapter*" | head -1)); test -f $A0/adapter_config.json || exit 1
W=/kaggle/working
train_arm() { torchrun --nproc_per_node 2 scripts/train_sft.py --model $MODEL --data runs/E04/sft_$1.jsonl --out $W/$2_adapter --init-adapter $A0 --max-steps 100 --grad-accum 8 --seed 0 > $W/$2_train.log 2>&1; test -f $W/$2_adapter/adapter_config.json; }
train_arm single-1 E04 || exit 1
train_arm targeted-4 E05 || exit 1
E="python scripts/run_rollouts.py --model $MODEL --spider-root $SPIDER"
( CUDA_VISIBLE_DEVICES=0 $E --adapter $W/E04_adapter --split data/splits/devB.jsonl --out $W/E04_devB.jsonl > $W/v0a.log 2>&1; CUDA_VISIBLE_DEVICES=0 $E --adapter $A0 --split data/splits/devB.jsonl --out $W/E01_devB.jsonl > $W/v0b.log 2>&1; CUDA_VISIBLE_DEVICES=0 $E --adapter $A0 --split data/splits/devA.jsonl --out $W/E01_devA.jsonl > $W/v0c.log 2>&1 ) &
( CUDA_VISIBLE_DEVICES=1 $E --adapter $W/E05_adapter --split data/splits/devB.jsonl --out $W/E05_devB.jsonl > $W/v1a.log 2>&1; CUDA_VISIBLE_DEVICES=1 $E --split data/splits/devB.jsonl --out $W/E00_devB.jsonl > $W/v1b.log 2>&1; CUDA_VISIBLE_DEVICES=1 $E --split data/splits/devA.jsonl --out $W/E00_devA.jsonl > $W/v1c.log 2>&1 ) &
wait; for f in $W/*.log; do echo $f; tail -n 2 $f; done; wc -l $W/*.jsonl
