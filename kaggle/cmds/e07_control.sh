set -x
ADP() { find /kaggle/input -name adapter_config.json | grep -v checkpoint | grep -i "$1" | head -1 | xargs -r dirname; }
A0=$(ADP e01-adapter); A4=$(ADP E04_adapter); A5=$(ADP E05_adapter); echo "A0=$A0 A4=$A4 A5=$A5"
test -f "$A0/adapter_config.json" || exit 1
W=/kaggle/working
torchrun --nproc_per_node 2 scripts/train_sft.py --model $MODEL --data runs/E07/sft_gold_matched.jsonl --out $W/E07_adapter --init-adapter $A0 --max-steps 100 --grad-accum 8 --seed 0 > $W/E07_train.log 2>&1
test -f $W/E07_adapter/adapter_config.json || exit 1
E="python scripts/run_rollouts.py --model $MODEL --spider-root $SPIDER"
L="$E --split data/splits/devB.jsonl --batch-size 1 --limit 60"
( CUDA_VISIBLE_DEVICES=0 $E --adapter $W/E07_adapter --split data/splits/devB.jsonl --out $W/E07_devB.jsonl > $W/v0a.log 2>&1; CUDA_VISIBLE_DEVICES=0 $L --adapter $W/E07_adapter --out $W/lat_E07.jsonl > $W/l0a.log 2>&1; test -n "$A5" && CUDA_VISIBLE_DEVICES=0 $L --adapter $A5 --out $W/lat_E05.jsonl > $W/l0b.log 2>&1 ) &
( CUDA_VISIBLE_DEVICES=1 $L --out $W/lat_E00.jsonl > $W/l1a.log 2>&1; CUDA_VISIBLE_DEVICES=1 $L --adapter $A0 --out $W/lat_E01.jsonl > $W/l1b.log 2>&1; test -n "$A4" && CUDA_VISIBLE_DEVICES=1 $L --adapter $A4 --out $W/lat_E04.jsonl > $W/l1c.log 2>&1 ) &
wait; cp $W/E07_adapter/train_summary.json $W/E07_train_summary.json; for f in $W/*.log; do echo $f; tail -n 2 $f; done; wc -l $W/*.jsonl
