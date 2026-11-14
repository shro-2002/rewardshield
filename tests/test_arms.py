import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_arm_sets import build_arms  # noqa: E402


def _verdicts(table):
    """table: {qid: [(single, targeted), ...per sample]}"""
    return [{"qid": q, "sample": i, "verdict": {"single-1": s, "targeted-4": t}}
            for q, rows in table.items() for i, (s, t) in enumerate(rows)]


TABLE = {
    "q1": [(True, True), (True, False)],
    "q2": [(True, False), (False, False)],   # single-only: the false-accept candidate
    "q3": [(True, True)],
    "q4": [(False, False)],
}


def test_arms_have_equal_size_equal_to_smallest_accepted_count():
    arms, _ = build_arms(_verdicts(TABLE), ["single-1", "targeted-4"], seed=0)
    assert len(arms["single-1"]) == len(arms["targeted-4"]) == 2  # targeted accepts q1, q3


def test_arm_only_contains_samples_its_verifier_accepted():
    verdicts = _verdicts(TABLE)
    accepted = {(v["qid"], v["sample"]) for v in verdicts if v["verdict"]["targeted-4"]}
    arms, _ = build_arms(verdicts, ["single-1", "targeted-4"], seed=0)
    assert set(arms["targeted-4"]) <= accepted


def test_one_sample_per_question_and_deterministic():
    a, _ = build_arms(_verdicts(TABLE), ["single-1", "targeted-4"], seed=0)
    b, _ = build_arms(_verdicts(TABLE), ["single-1", "targeted-4"], seed=0)
    assert a == b
    qids = [q for q, _ in a["single-1"]]
    assert len(qids) == len(set(qids))
