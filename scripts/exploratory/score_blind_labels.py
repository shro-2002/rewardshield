"""Score the filled blind-label CSV (exploratory, not pre-registered).

usage: .venv/bin/python scripts/exploratory/score_blind_labels.py [--csv runs/exploratory/blind_labels/to_label.csv]
       .venv/bin/python scripts/exploratory/score_blind_labels.py --selftest

Reports, joining on row_id with key.jsonl:
  - human vs oracle: agreement and Cohen's kappa, with `ambiguous` mapped to equivalent, to not_equivalent, or dropped
  - human vs Claude (rows with a Claude label): 3-class kappa, and the same binary mappings on both sides
  - miss rate in the all_accept stratum (human says not_equivalent although every verifier and the oracle accept),
    with a 95% Wilson interval; ambiguous counted as a miss and not counted
"""

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "runs/exploratory/blind_labels"
LABELS = ("equivalent", "not_equivalent", "ambiguous")
ALIASES = {"eq": "equivalent", "equiv": "equivalent", "ne": "not_equivalent", "not equivalent": "not_equivalent",
           "neq": "not_equivalent", "amb": "ambiguous"}


def norm_label(s: str) -> str | None:
    s = (s or "").strip().lower().replace("-", "_")
    s = ALIASES.get(s, s)
    if s and s not in LABELS:
        raise ValueError(f"unknown label {s!r}; use one of {LABELS}")
    return s or None


def kappa(pairs: list[tuple]) -> float | None:
    """Cohen's kappa for two raters over any label set; None when undefined (no pairs or chance agreement = 1)."""
    if not pairs:
        return None
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / n ** 2
    return None if pe == 1 else (po - pe) / (1 - pe)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float] | None:
    if n == 0:
        return None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def binarise(label: str, ambiguous_as: str | None) -> str | None:
    return ambiguous_as if label == "ambiguous" else label


def compare(pairs: list[tuple]) -> dict:
    """pairs of (label_a, label_b) with possible 'ambiguous'; report the three ambiguous policies."""
    out = {}
    for name, amb in (("ambiguous=equivalent", "equivalent"), ("ambiguous=not_equivalent", "not_equivalent"), ("ambiguous dropped", None)):
        bp = [(binarise(a, amb), binarise(b, amb)) for a, b in pairs]
        bp = [(a, b) for a, b in bp if a and b]
        out[name] = {"n": len(bp), "agreement": (sum(a == b for a, b in bp) / len(bp)) if bp else None, "kappa": kappa(bp)}
    return out


def score(csv_path: Path, key_path: Path) -> dict:
    key = {k["row_id"]: k for k in map(json.loads, open(key_path))}
    rows = [r for r in csv.DictReader(open(csv_path, newline=""))]
    lab = {r["row_id"]: norm_label(r["label"]) for r in rows}
    done = {rid: l for rid, l in lab.items() if l}
    res = {"rows": len(rows), "labelled": len(done), "human_label_counts": dict(Counter(done.values()))}
    orc = [(done[r], "equivalent" if key[r]["oracle"] else "not_equivalent") for r in done]
    res["human_vs_oracle"] = compare(orc)
    uni = [(done[r], "equivalent" if key[r]["union_oracle"] else "not_equivalent") for r in done if key[r].get("union_oracle") is not None]
    res["human_vs_union_oracle_devA"] = compare(uni)
    cl = [(done[r], key[r]["claude_label"]) for r in done if key[r].get("claude_label")]
    res["human_vs_claude"] = {"three_class": {"n": len(cl), "agreement": (sum(a == b for a, b in cl) / len(cl)) if cl else None,
                                              "kappa": kappa(cl)}, **compare(cl)}
    aa = [done[r] for r in done if key[r]["stratum"] == "all_accept"]
    strict, loose = sum(l == "not_equivalent" for l in aa), sum(l != "equivalent" for l in aa)
    res["all_accept_miss_rate"] = {"n": len(aa),
                                   "not_equivalent_only": {"k": strict, "rate": strict / len(aa) if aa else None, "wilson95": wilson(strict, len(aa))},
                                   "not_equivalent_or_ambiguous": {"k": loose, "rate": loose / len(aa) if aa else None, "wilson95": wilson(loose, len(aa))}}
    res["by_stratum"] = {s: dict(Counter(done[r] for r in done if key[r]["stratum"] == s))
                         for s in sorted({k["stratum"] for k in key.values()})}
    return res


def selftest() -> None:
    assert kappa([("a", "a"), ("b", "b")]) == 1.0
    assert abs(kappa([("a", "a"), ("a", "b"), ("b", "a"), ("b", "b")])) < 1e-12
    # textbook: 20 yes/yes, 5 yes/no, 10 no/yes, 15 no/no -> po=.7, pe=.5, kappa=.4
    pairs = [("y", "y")] * 20 + [("y", "n")] * 5 + [("n", "y")] * 10 + [("n", "n")] * 15
    assert abs(kappa(pairs) - 0.4) < 1e-12
    lo, hi = wilson(0, 20)
    assert lo == 0.0 and abs(hi - 0.1611) < 1e-3
    c = compare([("ambiguous", "equivalent"), ("not_equivalent", "not_equivalent")])
    assert c["ambiguous=equivalent"]["agreement"] == 1.0 and c["ambiguous=not_equivalent"]["agreement"] == 0.5
    assert c["ambiguous dropped"]["n"] == 1
    print("selftest ok")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=str(DIR / "to_label.csv"))
    ap.add_argument("--key", default=str(DIR / "key.jsonl"))
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        return
    print(json.dumps(score(Path(a.csv), Path(a.key)), indent=2))


if __name__ == "__main__":
    main()
