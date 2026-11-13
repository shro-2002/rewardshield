"""Phase 0 smoke test: model load, generation, AgentTune SQL rollout, AuditKIT import, LoRA step.

Run: uv run python scripts/smoke_phase0.py --model ~/models/tiny-aya-global --out runs/smoke_mac
Writes a JSON report and the raw trajectories to --out. Works on MPS (Mac) and CUDA (Kaggle).
"""

import argparse
import json
import os
import sqlite3
import tempfile
import time
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

TOY_SCHEMA = """
CREATE TABLE accounts (id INTEGER PRIMARY KEY, owner TEXT NOT NULL, country TEXT);
CREATE TABLE transactions (id INTEGER PRIMARY KEY, account_id INTEGER REFERENCES accounts(id),
                           amount REAL NOT NULL, kind TEXT);
INSERT INTO accounts VALUES (1,'Ana','Peru'),(2,'Bo','Chile'),(3,'Luz','Peru');
INSERT INTO transactions VALUES (1,1,120.0,'debit'),(2,1,30.0,'credit'),(3,2,75.5,'debit'),(4,3,10.0,'debit');
"""
QUESTIONS = [
    "How many accounts are owned by people in Peru?",
    "What is the total debit amount for the account owned by Ana?",
]
SYSTEM = (
    "You are a SQL agent for a SQLite database. Schema:\n" + TOY_SCHEMA.split("INSERT")[0]
    + "\nUse the run_sql tool to test queries. When done, reply with the final query in a ```sql block."
)


def pick_device() -> str:
    if torch.cuda.is_available():
        return "cuda"
    return "mps" if torch.backends.mps.is_available() else "cpu"


def make_db() -> str:
    path = os.path.join(tempfile.mkdtemp(), "toy.sqlite")
    with sqlite3.connect(path) as conn:
        conn.executescript(TOY_SCHEMA)
    return path


def make_tool(db_path: str):
    def run_sql(sql_command: str) -> list:
        """Run a read-only SQL query on the database and return up to 10 rows.

        Args:
            sql_command: The SQLite query to execute.
        """
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        deadline = time.monotonic() + 2.0
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
        try:
            return conn.execute(sql_command).fetchmany(10)
        except sqlite3.Error as exc:
            return [{"error": str(exc)}]
        finally:
            conn.close()

    return run_sql


def time_generation(model, tok, device: str, report: dict) -> None:
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": QUESTIONS[0]}]
    ids = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True).to(device)
    start = time.perf_counter()
    out = model.generate(**ids, max_new_tokens=128, do_sample=False)
    elapsed = time.perf_counter() - start
    new = out.shape[1] - ids["input_ids"].shape[1]
    report["generation"] = {
        "prompt_tokens": int(ids["input_ids"].shape[1]),
        "new_tokens": int(new),
        "seconds": round(elapsed, 2),
        "tokens_per_s": round(new / elapsed, 2),
        "text": tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True)[:600],
    }


def run_agenttune_rollout(model, tok, db_path: str, out_dir: Path, report: dict) -> list:
    from agenttune.agentic.rollout_engines.rollout_factory import create_rollout_engine, create_rollout_fn

    engine = create_rollout_engine(backend="transformers", model=model, tokenizer=tok)
    rollout_fn = create_rollout_fn(rollout_engine=engine, tools=[make_tool(db_path)], max_steps=4, system_prompt=SYSTEM)
    start = time.perf_counter()
    batch = rollout_fn(QUESTIONS)
    convs = batch["conversations"]
    report["rollout"] = {
        "seconds": round(time.perf_counter() - start, 2),
        "keys": sorted(batch.keys()),
        "tool_call_counts": list(batch["tool_call_counts"]),
        "responses": [str(r)[:400] for r in batch["responses"]],
    }
    with open(out_dir / "trajectories.jsonl", "w") as fh:
        for i, conv in enumerate(convs):
            fh.write(json.dumps({"id": f"smoke-{i}", "messages": conv}, default=str) + "\n")
    return convs


def import_into_auditkit(convs: list, report: dict) -> None:
    from auditkit.agent_eval.importers import episode_from_openai_messages

    episodes = [episode_from_openai_messages(c, case_id=f"smoke-{i}") for i, c in enumerate(convs)]
    report["auditkit"] = [
        {"case_id": e.case_id, "n_events": len(e.events), "event_types": sorted({ev.type for ev in e.events}),
         "final_answer": (e.final_answer or "")[:200]}
        for e in episodes
    ]


def lora_step(model, tok, device: str, report: dict) -> None:
    from peft import LoraConfig, get_peft_model

    peft_model = get_peft_model(model, LoraConfig(r=8, lora_alpha=16, target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM"))
    opt = torch.optim.AdamW([p for p in peft_model.parameters() if p.requires_grad], lr=1e-4)
    text = SYSTEM + "\n" + QUESTIONS[0] + "\n```sql\nSELECT COUNT(*) FROM accounts WHERE country = 'Peru';\n```"
    batch = tok(text, return_tensors="pt").to(device)
    losses, start = [], time.perf_counter()
    for _ in range(3):
        loss = peft_model(**batch, labels=batch["input_ids"]).loss
        loss.backward()
        opt.step()
        opt.zero_grad()
        losses.append(round(loss.item(), 4))
    report["lora"] = {"losses": losses, "seconds": round(time.perf_counter() - start, 2),
                      "finite": all(l == l and abs(l) < 1e4 for l in losses), "seq_len": int(batch["input_ids"].shape[1])}


def bench(model, tok, db_path: str, device: str, report: dict) -> None:
    """Throughput for planning: batched AgentTune rollouts and LoRA SFT steps at realistic length."""
    from agenttune.agentic.rollout_engines.rollout_factory import create_rollout_engine, create_rollout_fn
    from peft import LoraConfig, get_peft_model

    engine = create_rollout_engine(backend="transformers", model=model, tokenizer=tok)
    rollout_fn = create_rollout_fn(rollout_engine=engine, tools=[make_tool(db_path)], max_steps=4, system_prompt=SYSTEM)
    prompts = QUESTIONS * 4
    start = time.perf_counter()
    batch = rollout_fn(prompts)
    secs = time.perf_counter() - start
    report["bench_rollout"] = {"n": len(prompts), "seconds": round(secs, 1), "rollouts_per_min": round(60 * len(prompts) / secs, 1),
                               "mean_tool_calls": sum(batch["tool_call_counts"]) / len(prompts)}
    peft_model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, task_type="CAUSAL_LM",
                                                  target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]))
    peft_model.gradient_checkpointing_enable()
    peft_model.enable_input_require_grads()
    opt = torch.optim.AdamW([p for p in peft_model.parameters() if p.requires_grad], lr=1e-4)
    seq = (SYSTEM + " ") * 6
    ids = tok([seq] * 2, return_tensors="pt", truncation=True, max_length=1024).to(device)
    start = time.perf_counter()
    for _ in range(5):
        peft_model(**ids, labels=ids["input_ids"]).loss.backward()
        opt.step()
        opt.zero_grad()
    secs = time.perf_counter() - start
    report["bench_lora"] = {"batch": 2, "seq_len": int(ids["input_ids"].shape[1]), "steps": 5, "seconds": round(secs, 1),
                            "train_tokens_per_s": round(5 * 2 * ids["input_ids"].shape[1] / secs, 1)}
    if device == "cuda":
        report["bench_peak_mem_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", default="runs/smoke")
    ap.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    ap.add_argument("--bench", action="store_true")
    args = ap.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    device = pick_device()
    report: dict = {"device": device, "dtype": args.dtype, "torch": torch.__version__}

    tok = AutoTokenizer.from_pretrained(os.path.expanduser(args.model))
    report["chat_template_present"] = bool(tok.chat_template)
    start = time.perf_counter()
    model = AutoModelForCausalLM.from_pretrained(os.path.expanduser(args.model), dtype=getattr(torch, args.dtype)).to(device)
    report["load_seconds"] = round(time.perf_counter() - start, 1)
    report["architecture"] = type(model).__name__
    if device == "cuda":
        report["cuda_mem_gb_after_load"] = round(torch.cuda.memory_allocated() / 1e9, 2)

    steps = [("generation", lambda: time_generation(model, tok, device, report))]
    db_path = make_db()
    convs: list = []

    def rollout():
        convs.extend(run_agenttune_rollout(model, tok, db_path, out_dir, report))

    steps += [("rollout", rollout), ("auditkit", lambda: import_into_auditkit(convs, report)),
              ("lora", lambda: lora_step(model, tok, device, report))]
    if args.bench:  # runs on a fresh model so the smoke LoRA above does not stack
        steps.append(("bench", lambda: bench(
            AutoModelForCausalLM.from_pretrained(os.path.expanduser(args.model), dtype=getattr(torch, args.dtype)).to(device),
            tok, db_path, device, report)))
    for name, fn in steps:
        try:
            fn()
        except Exception as exc:  # each stage is reported, not hidden; later stages still run
            report[f"{name}_error"] = f"{type(exc).__name__}: {exc}"[:800]
    (out_dir / "smoke_report.json").write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps(report, indent=2, default=str)[:6000])


if __name__ == "__main__":
    main()
