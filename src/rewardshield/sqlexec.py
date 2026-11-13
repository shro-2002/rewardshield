"""Isolated, read-only SQLite execution and result comparison."""

from __future__ import annotations

import itertools
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass

import sqlglot
from sqlglot import exp

DEFAULT_TIMEOUT_S = 2.0
MAX_ROWS = 20_000
FLOAT_DIGITS = 6
MAX_PERMUTED_COLUMNS = 6
MAX_VALUE_BYTES = 1_000_000  # largest single string/blob a query may build
MAX_SQL_BYTES = 100_000
MAX_RESULT_BYTES = 20_000_000
FETCH_BATCH = 1_000

_DENIED_ACTIONS = {
    sqlite3.SQLITE_ATTACH, sqlite3.SQLITE_DETACH, sqlite3.SQLITE_INSERT, sqlite3.SQLITE_UPDATE,
    sqlite3.SQLITE_DELETE, sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_ALTER_TABLE, sqlite3.SQLITE_TRANSACTION, sqlite3.SQLITE_PRAGMA,
}


@dataclass(frozen=True)
class ExecResult:
    rows: tuple[tuple, ...] | None
    error: str | None
    ms: float

    @property
    def ok(self) -> bool:
        return self.error is None


def _authorizer(action: int, *_args) -> int:
    return sqlite3.SQLITE_DENY if action in _DENIED_ACTIONS else sqlite3.SQLITE_OK


def execute(db_path: str, sql: str, timeout_s: float = DEFAULT_TIMEOUT_S) -> ExecResult:
    """Run one statement read-only with a time limit and a row cap. Never raises for bad SQL."""
    start = time.perf_counter()
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    except sqlite3.Error as exc:
        return ExecResult(None, f"connect: {exc}", 0.0)
    try:
        conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
        conn.set_authorizer(_authorizer)
        # Model-written SQL is untrusted: cap value size and statement size, not only time.
        conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_VALUE_BYTES)
        conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, MAX_SQL_BYTES)
        deadline = time.monotonic() + timeout_s
        conn.set_progress_handler(lambda: int(time.monotonic() > deadline), 5_000)
        cur = conn.execute(sql)
        rows: list[tuple] = []
        result_bytes = 0
        while batch := cur.fetchmany(FETCH_BATCH):
            rows.extend(tuple(r) for r in batch)
            result_bytes += sum(_approx_bytes(v) for r in batch for v in r)
            if len(rows) > MAX_ROWS or result_bytes > MAX_RESULT_BYTES:
                return ExecResult(None, "result too large", _ms(start))
        return ExecResult(tuple(rows), None, _ms(start))
    except (sqlite3.Error, sqlite3.Warning, ValueError, OverflowError) as exc:
        return ExecResult(None, f"{type(exc).__name__}: {exc}"[:300], _ms(start))
    finally:
        conn.close()


def _approx_bytes(value: object) -> int:
    return len(value) if isinstance(value, (str, bytes)) else 8


def _ms(start: float) -> float:
    return (time.perf_counter() - start) * 1000


def _norm(value: object) -> object:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, float):
        return int(value) if value.is_integer() else round(value, FLOAT_DIGITS)
    return value


def _normalise(rows: tuple[tuple, ...]) -> list[tuple]:
    return [tuple(_norm(v) for v in row) for row in rows]


def has_top_level_order(sql: str) -> bool:
    """True when the outermost query has ORDER BY, so row order is part of the answer."""
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except sqlglot.errors.ParseError:
        return "order by" in sql.lower()
    return tree.args.get("order") is not None


def results_match(gold: tuple[tuple, ...], pred: tuple[tuple, ...], ordered: bool) -> bool:
    """Multiset (or list, if ordered) equality, ignoring column order.

    Duplicates count. Floats are compared after rounding. Column permutations are tried only
    when the column counts match and there are at most MAX_PERMUTED_COLUMNS columns.
    """
    g, p = _normalise(gold), _normalise(pred)
    if len(g) != len(p):
        return False
    if not g:
        return True
    ncols = len(g[0])
    if any(len(r) != ncols for r in p):
        return False
    perms = [tuple(range(ncols))]
    if 1 < ncols <= MAX_PERMUTED_COLUMNS:
        perms = list(itertools.permutations(range(ncols)))
    gold_cmp = g if ordered else Counter(g)
    for perm in perms:
        permuted = [tuple(row[i] for i in perm) for row in p]
        if (permuted if ordered else Counter(permuted)) == gold_cmp:
            return True
    return False


def literals(sql: str) -> list[object]:
    """String and numeric literals in a query, used to seed generated databases."""
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except sqlglot.errors.ParseError:
        return []
    out: list[object] = []
    for lit in tree.find_all(exp.Literal):
        if lit.is_string:
            out.append(lit.this)
        else:
            try:
                num = float(lit.this)
            except ValueError:
                continue
            out.append(int(num) if num.is_integer() else num)
    return out
