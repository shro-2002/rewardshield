"""Batched multi-turn SQL-agent rollouts in AgentTune's Tiny Aya format.

AgentTune's rollout_fn generates one conversation at a time. For a pool of thousands of rollouts
on one T4 we batch generation across conversations, while keeping AgentTune's pieces: its tool
fallback system prompt, its tool-call parser (extract_tool_calls_from_text) and its tool-result
format. Parity with AgentTune's rollout_fn under greedy decoding is checked by
scripts/check_rollout_parity.py.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import torch
from agenttune.agentic.rollout_engines.tool_call_parse import extract_tool_calls_from_text

from .agent import TOOL_RESULT_FORMAT, final_sql, full_system_prompt, make_run_sql


@dataclass
class Episode:
    qid: str
    sample: int
    db_path: str
    messages: list[dict]
    done: bool = False
    n_tool_calls: int = 0
    gen_tokens: int = 0
    seconds: float = 0.0
    tool: object = field(default=None, repr=False)

    def record(self) -> dict:
        return {"qid": self.qid, "sample": self.sample, "final_sql": final_sql(self.messages),
                "n_tool_calls": self.n_tool_calls, "gen_tokens": self.gen_tokens, "messages": self.messages}


def _start(item: dict, sample: int) -> Episode:
    msgs = [{"role": "system", "content": full_system_prompt(item["db_path"])},
            {"role": "user", "content": item["question"]}]
    return Episode(item["qid"], sample, item["db_path"], msgs, tool=make_run_sql(item["db_path"]))


def _apply_turn(ep: Episode, text: str, last_step: bool) -> None:
    calls = extract_tool_calls_from_text(text) or []
    calls = [c for c in calls if (c.get("function") or {}).get("name") == "run_sql"]
    if not calls:
        ep.messages.append({"role": "assistant", "content": text})
        ep.done = True
        return
    ep.messages.append({"role": "assistant", "content": text, "tool_calls": calls})
    results = []
    for call in calls:
        args = (call.get("function") or {}).get("arguments")
        sql = _sql_arg(args)
        results.append(TOOL_RESULT_FORMAT.format(name="run_sql", content=ep.tool(sql) if sql else [{"error": "missing sql_command"}]))
        ep.n_tool_calls += 1
    ep.messages.append({"role": "user", "content": "\n".join(results)})
    ep.done = last_step


def _sql_arg(args: object) -> str:
    import json

    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return ""
    return str(args.get("sql_command", "")) if isinstance(args, dict) else ""


def stop_token_ids(model, tok) -> list[int]:
    """Stop at the model's configured EOS and at the chat template's end-of-turn token.

    Tiny Aya's generation_config stops on <EOS_TOKEN> (id 3) only, but a chat turn ends with
    <|END_OF_TURN_TOKEN|> (tok.eos_token, id 6). Without id 6 the model runs on into the next turn
    and writes a fake tool result itself (DECISIONS.md 2026-11-14 22:50).
    """
    configured = model.generation_config.eos_token_id
    configured = configured if isinstance(configured, list) else [configured]
    return sorted({i for i in [*configured, tok.eos_token_id] if i is not None})


@torch.no_grad()
def _generate(model, tok, convs: list[list[dict]], *, temperature: float, max_new_tokens: int) -> tuple[list[str], list[int]]:
    texts = [tok.apply_chat_template(c, add_generation_prompt=True, tokenize=False) for c in convs]
    enc = tok(texts, return_tensors="pt", padding=True, add_special_tokens=False).to(model.device)
    sample = temperature > 0
    out = model.generate(**enc, max_new_tokens=max_new_tokens, do_sample=sample,
                         temperature=temperature if sample else None, top_p=1.0 if sample else None,
                         pad_token_id=tok.pad_token_id, eos_token_id=stop_token_ids(model, tok))
    new = out[:, enc["input_ids"].shape[1]:]
    decoded = tok.batch_decode(new, skip_special_tokens=True)
    lengths = [int((row != tok.pad_token_id).sum()) for row in new]
    return [d.strip() for d in decoded], lengths


def run_rollouts(model, tok, items: list[dict], *, n: int = 1, temperature: float = 0.0, max_steps: int = 4,
                 max_new_tokens: int = 192, batch_size: int = 16, on_done=None) -> list[dict]:
    """Roll out n samples per item. Each item needs qid, question, db_path. Returns records."""
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    episodes = [_start(item, s) for item in items for s in range(n)]
    episodes.sort(key=lambda e: len(e.messages[0]["content"]))  # similar lengths batch together
    records = []
    for i in range(0, len(episodes), batch_size):
        batch, start = episodes[i:i + batch_size], time.perf_counter()
        for step in range(max_steps):
            active = [e for e in batch if not e.done]
            if not active:
                break
            texts, lengths = _generate(model, tok, [e.messages for e in active],
                                       temperature=temperature, max_new_tokens=max_new_tokens)
            for ep, text, length in zip(active, texts, lengths):
                ep.gen_tokens += length
                _apply_turn(ep, text, last_step=step == max_steps - 1)
        elapsed = time.perf_counter() - start
        for ep in batch:
            ep.seconds = elapsed / len(batch)
            rec = ep.record()
            records.append(rec)
            if on_done:
                on_done(rec)
    return records
