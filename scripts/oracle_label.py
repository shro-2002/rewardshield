"""Label rollout samples with the independent oracle (oracle/oracle.py, run in its own venv).

A sample with no committed SQL is labelled False. Output rows: qid, sample, db_id, oracle.
uv run python scripts/oracle_label.py --samples runs/E01/devB.jsonl --split data/splits/devB.jsonl --out runs/E01/devB_oracle.jsonl
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from rewardshield.data import load_split  # noqa: E402

ORACLE_PY = ROOT / "oracle" / ".venv" / "bin" / "python"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    questions = {r["qid"]: r for r in load_split(args.split)}
    samples = [json.loads(line) for line in open(args.samples)]
    with tempfile.TemporaryDirectory() as tmp:
        pairs, verdicts = Path(tmp, "pairs.jsonl"), Path(tmp, "verdicts.jsonl")
        with pairs.open("w") as fh:
            for s in samples:
                if s.get("final_sql"):
                    q = questions[s["qid"]]
                    fh.write(json.dumps({"qid": f"{s['qid']}#{s['sample']}", "db_id": q["db_id"],
                                         "gold": q["gold"], "pred": s["final_sql"]}) + "\n")
        subprocess.run([str(ORACLE_PY), str(ROOT / "oracle" / "oracle.py"), "--pairs", str(pairs), "--out", str(verdicts)],
                       check=True, cwd=ROOT)
        labels = {v["qid"]: v["verdict"] for v in map(json.loads, verdicts.open())}
    with open(args.out, "w") as fh:
        for s in samples:
            key = f"{s['qid']}#{s['sample']}"
            label = labels.get(key) if s.get("final_sql") else False
            fh.write(json.dumps({"qid": s["qid"], "sample": s["sample"], "db_id": questions[s["qid"]]["db_id"],
                                 "oracle": label}) + "\n")
    n_true = sum(1 for s in samples if labels.get(f"{s['qid']}#{s['sample']}"))
    print(json.dumps({"samples": len(samples), "oracle_true": n_true, "accuracy": n_true / max(len(samples), 1)}))


if __name__ == "__main__":
    main()
