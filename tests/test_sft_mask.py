from types import SimpleNamespace

import pytest

from rewardshield.rollout import stop_token_ids
from rewardshield.sft_mask import assistant_char_spans, token_mask

CONV = [
    {"role": "system", "content": "S"},
    {"role": "user", "content": "Q"},
    {"role": "assistant", "content": "CALL"},
    {"role": "user", "content": "RESULT"},
    {"role": "assistant", "content": "ANSWER"},
]


def render(msgs, gen):
    """Tiny prefix-stable template: <role>content</> per turn, '<assistant>' as generation prompt."""
    text = "".join(f"<{m['role']}>{m['content']}</>" for m in msgs)
    return text + ("<assistant>" if gen else "")


def test_assistant_spans_cover_assistant_turns_but_not_tool_results():
    full = render(CONV, False)
    spans = assistant_char_spans(render, CONV)
    covered = "".join(full[s:e] for s, e in spans)
    assert covered == "CALL</>ANSWER</>"
    assert "RESULT" not in covered


def test_token_mask_marks_only_tokens_inside_spans():
    offsets = [(0, 2), (2, 4), (4, 6), (6, 6)]  # last one is a zero-width special token
    assert token_mask(offsets, [(2, 5)]) == [0, 1, 1, 0]


def test_non_prefix_stable_template_is_rejected():
    def unstable(msgs, gen):
        return render(msgs, gen) + ("<eos>" if not gen else "")

    with pytest.raises(ValueError):
        assistant_char_spans(unstable, CONV)


def test_stop_ids_include_end_of_turn_token():
    model = SimpleNamespace(generation_config=SimpleNamespace(eos_token_id=3))
    tok = SimpleNamespace(eos_token_id=6)
    assert stop_token_ids(model, tok) == [3, 6]
