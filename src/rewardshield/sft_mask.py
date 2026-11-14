"""Loss mask for agent SFT: train on assistant turns only, never on tool results.

Tool results come from the environment. Training on them teaches the model to write tool results
itself (it did, in E01; DECISIONS.md 2026-11-14 22:50). AgentTune masks them the same way (env_mask).
"""

from collections.abc import Callable

Render = Callable[[list[dict], bool], str]  # (messages, add_generation_prompt) -> chat-template text


def assistant_char_spans(render: Render, msgs: list[dict]) -> list[tuple[int, int]]:
    """Character spans of every assistant turn in render(msgs), including its end-of-turn tokens."""
    full = render(msgs, False)
    spans = []
    for i, msg in enumerate(msgs):
        if msg["role"] != "assistant":
            continue
        start_text, end_text = render(msgs[:i], True), render(msgs[: i + 1], False)
        if not (full.startswith(start_text) and full.startswith(end_text)):
            raise ValueError(f"chat template is not prefix-stable at message {i}; cannot locate the assistant turn")
        spans.append((len(start_text), len(end_text)))
    return spans


def token_mask(offsets: list[tuple[int, int]], spans: list[tuple[int, int]]) -> list[int]:
    """1 for tokens that start inside an assistant span, else 0."""
    return [int(any(s <= start < e for s, e in spans) and end > start) for start, end in offsets]


def tokenize_with_assistant_mask(tok, msgs: list[dict]) -> dict:
    """input_ids plus TRL's `assistant_masks` column for one conversation."""
    def render(m: list[dict], gen: bool) -> str:
        return tok.apply_chat_template(m, tokenize=False, add_generation_prompt=gen)

    text = render(msgs, False)
    enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
    mask = token_mask(enc["offset_mapping"], assistant_char_spans(render, msgs))
    return {"input_ids": enc["input_ids"], "assistant_masks": mask}
