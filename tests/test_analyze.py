import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("analyze", Path(__file__).resolve().parents[1] / "scripts" / "analyze.py")
analyze = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyze)


def _row(qid, oracle, single, targeted):
    return {"qid": qid, "oracle": oracle, "verdict": {"single-1": single, "targeted-4": targeted}}


def test_verifier_metrics_definitions():
    rows = [_row("a", True, True, True), _row("b", False, True, False), _row("c", False, False, False), _row("d", True, False, True)]
    m = analyze.verifier_metrics(rows, "single-1")
    assert m["accepted"] == 2 and m["false_accept_share"] == 0.5 and m["false_accept_mass"] == 0.25
    assert m["false_reject_rate"] == 0.5 and m["coverage"] == 0.5


def test_bootstrap_detects_clear_difference():
    rows = [_row(f"q{i}", i % 2 == 0, True, i % 2 == 0) for i in range(200)]
    point, lo, hi = analyze.bootstrap(analyze._by(rows, "qid"), analyze.fa_share_diff("single-1", "targeted-4"), n_boot=500)
    assert point == -0.5 and hi < 0
    assert analyze.verdict_label(lo, hi, -1) == "supported"
    assert analyze.verdict_label(-0.1, 0.1, -1) == "inconclusive"
