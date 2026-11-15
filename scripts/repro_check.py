"""Fresh reproducibility check: re-derive every headline number from stored artifacts and compare.

uv run python scripts/repro_check.py [--with-exploratory]     # writes runs/repro_check/report.json, exits 1 on mismatch
Runs the test suite, the pre-registered analyses (analyze.py), oracle accuracies per model, and optionally the
seed-averaged audit (scripts/exploratory/audit5.py, several minutes). GPU steps are not re-run.
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
TOL = 0.0006  # numbers in RESULTS.md are rounded to 0.01 points (shares) or 0.1 points (accuracy)

EXPECTED_SHARES = {"single-1": 0.0388, "agenttune": 0.0431, "random-4": 0.0313, "targeted-4": 0.0139, "random-16": 0.0100}
EXPECTED_TESTS = {"H1 targeted-4 vs single-1": -0.0248, "H2 targeted-4 vs random-4": -0.0174}
EXPECTED_ACC = {"E00": 0.515, "E01": 0.596, "E04": 0.631, "E05": 0.620}
EXPECTED_H3 = (-0.0106, -0.0422, 0.0185)
EXPECTED_E07 = 0.594
EXPECTED_AUDIT5 = {"devA": -0.25, "devB": -1.57}


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)


def close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def check_tests(checks: list) -> None:
    out = run([PY, "-m", "pytest", "-q"])
    tail = out.stdout.strip().splitlines()[-1] if out.stdout else out.stderr[-200:]
    checks.append(("pytest", out.returncode == 0, tail))


def check_verifiers(checks: list) -> None:
    out = run([PY, "scripts/analyze.py", "verifiers", "--verdicts", "runs/E03/verdicts_devA.jsonl", "--oracle", "runs/E03/oracle_devA.jsonl"])
    res = json.loads(out.stdout)
    for k, v in EXPECTED_SHARES.items():
        got = res["metrics"][k]["false_accept_share"]
        checks.append((f"E03 FA share {k}", close(got, v), round(got, 4)))
    for k, v in EXPECTED_TESTS.items():
        got = res["tests"][k]
        checks.append((f"E03 {k}", close(got["diff"], v) and got["result"] == "supported", [round(got["diff"], 4), got["result"]]))


def check_arms(checks: list) -> None:
    for m, v in EXPECTED_ACC.items():
        rows = [json.loads(line) for line in open(ROOT / f"runs/E04/out/{m}_devB_oracle.jsonl")]
        got = sum(bool(r["oracle"]) for r in rows) / len(rows)
        checks.append((f"dev-B accuracy {m}", close(got, v, 0.0006), round(got, 4)))
    out = run([PY, "scripts/analyze.py", "arms", "--a", "runs/E04/out/E04_devB_oracle.jsonl", "--b", "runs/E04/out/E05_devB_oracle.jsonl"])
    res = json.loads(out.stdout)
    d, (lo, hi) = res["diff_question"]["diff"], res["diff_question"]["ci95"]
    ok = close(d, EXPECTED_H3[0]) and close(lo, EXPECTED_H3[1]) and close(hi, EXPECTED_H3[2]) and res["H3"] == "inconclusive"
    checks.append(("H3 E05 - E04", ok, [round(d, 4), round(lo, 4), round(hi, 4), res["H3"]]))
    e07 = ROOT / "runs/E07/out/E07_devB_oracle.jsonl"
    if e07.exists():
        rows = [json.loads(line) for line in open(e07)]
        got = sum(bool(r["oracle"]) for r in rows) / len(rows)
        checks.append(("dev-B accuracy E07", len(rows) == 379 and close(got, EXPECTED_E07, 0.0006), round(got, 4)))
    else:
        checks.append(("dev-B accuracy E07", False, "runs/E07/out/E07_devB_oracle.jsonl missing"))


def check_audit5(checks: list) -> None:
    with tempfile.TemporaryDirectory() as cache:
        out = run([PY, "scripts/exploratory/audit5.py", cache])
    found = dict(re.findall(r"=== (dev[AB]):.*?H2 diff ([+-][0-9.]+) pts", out.stdout, flags=re.S))
    for split, v in EXPECTED_AUDIT5.items():
        got = float(found.get(split, "nan"))
        checks.append((f"seed-averaged H2 {split}", close(got, v, 0.006), got))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-exploratory", action="store_true")
    args = ap.parse_args()
    checks: list = []
    check_tests(checks)
    check_verifiers(checks)
    check_arms(checks)
    if args.with_exploratory:
        check_audit5(checks)
    out = ROOT / "runs/repro_check"
    out.mkdir(parents=True, exist_ok=True)
    report = [{"check": c, "ok": ok, "value": v} for c, ok, v in checks]
    (out / "report.json").write_text(json.dumps(report, indent=1))
    for r in report:
        print(("PASS " if r["ok"] else "FAIL ") + r["check"], r["value"])
    sys.exit(0 if all(r["ok"] for r in report) else 1)


if __name__ == "__main__":
    main()
