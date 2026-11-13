"""Single, random-k and targeted-k verifiers over a shared per-question candidate set.

For each gold query we build N_CANDIDATES schema-preserving databases (seeded by question id and
the gold literals). random-k keeps the original database plus k-1 candidates drawn at random;
targeted-k keeps the original plus up to k-1 candidates chosen greedily to kill the most gold
mutants. Both draw from the same candidates, so they differ only in the selection rule.
Agreement on a finite set of databases is evidence, not proof, of equivalence.
"""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass, field
from pathlib import Path

from .dbgen import generate_db, read_schema, sample_values
from .mutants import generate_mutants
from .sqlexec import ExecResult, execute, has_top_level_order, literals, results_match

N_CANDIDATES = 24


@dataclass(frozen=True)
class Verdict:
    accept: bool
    n_exec: int
    ms: float
    reason: str


@dataclass
class QuestionSuite:
    """Everything a verifier needs for one gold query, built once and cached."""
    qid: str
    gold_sql: str
    original_db: str
    candidates: list[str]
    gold_results: dict[str, ExecResult]
    ordered: bool
    targeted_order: list[str] = field(default_factory=list)  # greedy pick order
    mutant_kills: dict[str, int] = field(default_factory=dict)  # db -> new kills when picked
    n_mutants: int = 0
    n_killed: int = 0
    build_seconds: float = 0.0

    def databases(self, mode: str, k: int) -> list[str]:
        if mode == "single" or k <= 1:
            return [self.original_db]
        if mode == "random":
            rng = random.Random(_seed(self.qid, "random"))
            usable = [c for c in self.candidates if self.gold_results[c].ok]
            return [self.original_db] + rng.sample(usable, min(k - 1, len(usable)))
        if mode == "targeted":
            return [self.original_db] + self.targeted_order[: k - 1]
        raise ValueError(f"unknown mode {mode}")


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:12], 16)


def _columns_by_table(tables) -> dict[str, list[str]]:
    return {t.name: [c.name for c in t.columns] for t in tables}


def build_suite(qid: str, gold_sql: str, original_db: str, cache_dir: str,
                n_candidates: int = N_CANDIDATES, schema_cache: dict | None = None) -> QuestionSuite:
    start = time.perf_counter()
    schema_cache = schema_cache if schema_cache is not None else {}
    if original_db not in schema_cache:
        tables = read_schema(original_db)
        schema_cache[original_db] = (tables, sample_values(original_db, tables))
    tables, originals = schema_cache[original_db]
    gold_lits = literals(gold_sql)
    out_dir = Path(cache_dir) / qid
    candidates = []
    for i in range(n_candidates):
        path = str(out_dir / f"cand_{i:02d}.sqlite")
        if not Path(path).exists():
            generate_db(original_db, path, seed=_seed(qid, str(i)), gold_literals=gold_lits,
                        tables=tables, originals=originals)
        candidates.append(path)
    gold_results = {db: execute(db, gold_sql) for db in [original_db] + candidates}
    suite = QuestionSuite(qid, gold_sql, original_db, candidates, gold_results, has_top_level_order(gold_sql))
    _select_targeted(suite, generate_mutants(gold_sql, _columns_by_table(tables)))
    suite.build_seconds = time.perf_counter() - start
    return suite


def _differs(gold: ExecResult, other: ExecResult, ordered: bool) -> bool:
    if not gold.ok:
        return False
    return (not other.ok) or not results_match(gold.rows, other.rows, ordered)


def _select_targeted(suite: QuestionSuite, mutants: list[str]) -> None:
    """Greedy set cover: keep the candidate that kills the most not-yet-killed mutants."""
    usable = [c for c in suite.candidates if suite.gold_results[c].ok]
    orig = suite.gold_results[suite.original_db]
    # Mutants the original database already kills are not targets; single already catches them.
    live = [m for m in mutants if not _differs(orig, execute(suite.original_db, m), suite.ordered)]
    kills = {c: {i for i, m in enumerate(live) if _differs(suite.gold_results[c], execute(c, m), suite.ordered)}
             for c in usable}
    suite.n_mutants, remaining = len(live), set(range(len(live)))
    while remaining:
        best = max(usable, key=lambda c: (len(kills[c] & remaining), -usable.index(c)), default=None)
        if best is None or not kills[best] & remaining:
            break
        suite.mutant_kills[best] = len(kills[best] & remaining)
        remaining -= kills[best]
        suite.targeted_order.append(best)
        usable.remove(best)
    suite.n_killed = suite.n_mutants - len(remaining)
    # Fill unused slots so targeted-k spends the same database budget as random-k: informative
    # candidates first (gold returns rows that are not all NULL), in a seeded order.
    rng = random.Random(_seed(suite.qid, "fill"))
    rng.shuffle(usable)
    usable.sort(key=lambda c: not _informative(suite.gold_results[c]))
    suite.targeted_order.extend(usable)


def _informative(res: ExecResult) -> bool:
    return bool(res.rows) and any(v is not None for row in res.rows for v in row)


def verify(suite: QuestionSuite, pred_sql: str, mode: str, k: int = 4) -> Verdict:
    """Accept iff pred matches gold on every database the mode selects. Stops at the first mismatch."""
    start, n = time.perf_counter(), 0
    for db in suite.databases(mode, k):
        gold = suite.gold_results.get(db) or execute(db, suite.gold_sql)
        if not gold.ok:
            continue  # a database where gold itself fails says nothing about pred
        n += 1
        pred = execute(db, pred_sql)
        if not pred.ok:
            return Verdict(False, n, _ms(start), f"pred error: {pred.error}")
        if not results_match(gold.rows, pred.rows, suite.ordered):
            return Verdict(False, n, _ms(start), f"mismatch on {Path(db).name}")
    return Verdict(n > 0, n, _ms(start), "match" if n else "gold failed everywhere")


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000
