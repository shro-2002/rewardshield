"""LoRA SFT on agent trajectories (TRL SFTTrainer). Loss is on the completion: every turn after the
question (tool calls, tool results, final reply). Examples longer than --max-length are dropped and
counted, never truncated.

uv run python scripts/train_sft.py --model ~/models/tiny-aya-global --data runs/E01/sft_gold.jsonl \
    --out runs/E01/adapter [--init-adapter runs/E01/adapter] --max-steps 300 --seed 0
"""

import argparse
import json
import os
import time
from pathlib import Path

import torch
from datasets import Dataset
from peft import LoraConfig, PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTConfig, SFTTrainer

LORA_TARGETS = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"]


def load_examples(path: str, tok, max_length: int) -> tuple[list[dict], dict]:
    kept, stats = [], {"read": 0, "dropped_too_long": 0}
    for line in open(path):
        msgs = json.loads(line)["messages"]
        stats["read"] += 1
        n_tokens = len(tok.apply_chat_template(msgs, tokenize=True, return_dict=True)["input_ids"])
        if n_tokens > max_length:
            stats["dropped_too_long"] += 1
            continue
        kept.append({"prompt": msgs[:2], "completion": msgs[2:]})
    stats["kept"] = len(kept)
    return kept, stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--init-adapter", help="continue training this LoRA adapter (arms start from the warm start)")
    ap.add_argument("--max-steps", type=int, default=300)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=3072)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    cuda = torch.cuda.is_available()
    model_path = os.path.expanduser(args.model)
    tok = AutoTokenizer.from_pretrained(model_path)
    examples, stats = load_examples(args.data, tok, args.max_length)
    model = AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.float16 if cuda else torch.bfloat16)
    peft_config = None
    if args.init_adapter:
        model = PeftModel.from_pretrained(model, args.init_adapter, is_trainable=True)
    else:
        peft_config = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules=LORA_TARGETS, task_type="CAUSAL_LM")
    config = SFTConfig(
        output_dir=args.out, max_steps=args.max_steps, learning_rate=args.lr, lr_scheduler_type="cosine",
        warmup_ratio=0.05, per_device_train_batch_size=args.batch_size, gradient_accumulation_steps=args.grad_accum,
        gradient_checkpointing=True, fp16=cuda, bf16=False, max_length=args.max_length, completion_only_loss=True,
        logging_steps=10, save_strategy="steps", save_steps=100, save_total_limit=1, seed=args.seed,
        report_to="none", dataset_num_proc=1,
    )
    trainer = SFTTrainer(model=model, args=config, train_dataset=Dataset.from_list(examples),
                         processing_class=tok, peft_config=peft_config)
    start = time.perf_counter()
    result = trainer.train()
    trainer.save_model(args.out)
    summary = {**stats, "seed": args.seed, "max_steps": args.max_steps, "lr": args.lr,
               "effective_batch": args.batch_size * args.grad_accum, "seconds": round(time.perf_counter() - start, 1),
               "train_loss": result.training_loss, "init_adapter": args.init_adapter,
               "train_tokens_seen": trainer.state.num_input_tokens_seen,
               "log_tail": trainer.state.log_history[-5:]}
    Path(args.out, "train_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, default=str)[:2000])


if __name__ == "__main__":
    main()
