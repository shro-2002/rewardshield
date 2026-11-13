"""Schema-preserving random database generation for SQLite.

Generated databases keep every table, column, declared type, primary key, NOT NULL, UNIQUE
index and foreign key of the original. Values are drawn from the original column values, from
literals in the gold query (so its filters can match) and from boundary variants of numeric
literals. Small tables expose differences that large ones hide (same idea as Zhong et al. 2020).
"""

from __future__ import annotations

import random
import shutil
import sqlite3
from dataclasses import dataclass, field
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

NULL_PROB = 0.15
DUP_PROB = 0.3
MAX_SAMPLED_VALUES = 40
MAX_ROWS_PER_TABLE = 8
EMPTY_TABLE_PROB = 0.1


@dataclass(frozen=True)
class Column:
    name: str
    decl_type: str
    not_null: bool
    pk: bool


@dataclass
class Table:
    name: str
    columns: list[Column]
    unique_sets: list[tuple[str, ...]] = field(default_factory=list)
    fks: list[tuple[str, str, str]] = field(default_factory=list)  # (column, parent_table, parent_column)


def _q(name: str) -> str:
    # Identifiers cannot be bound as parameters; names come only from the database's own sqlite_master.
    return '"' + name.replace('"', '""') + '"'


def _connect_read_only(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace")
    return conn


def read_schema(db_path: str) -> list[Table]:
    conn = _connect_read_only(db_path)
    try:
        names = [r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        tables = []
        for name in names:
            cols = [Column(r[1], (r[2] or "").upper(), bool(r[3]), r[5] > 0)
                    for r in conn.execute("SELECT * FROM pragma_table_info(?)", (name,))]
            table = Table(name, cols)
            pk = tuple(c.name for c in cols if c.pk)
            if pk:
                table.unique_sets.append(pk)
            for idx in conn.execute("SELECT * FROM pragma_index_list(?)", (name,)):
                if idx[2]:  # unique
                    idx_cols = tuple(r[2] for r in conn.execute("SELECT * FROM pragma_index_info(?)", (idx[1],)))
                    if idx_cols and idx_cols not in table.unique_sets:
                        table.unique_sets.append(idx_cols)
            for fk in conn.execute("SELECT * FROM pragma_foreign_key_list(?)", (name,)):
                table.fks.append((fk[3], fk[2], fk[4] or ""))
            tables.append(table)
        return tables
    finally:
        conn.close()


def _kind(decl_type: str) -> str:
    t = decl_type.upper()
    if "INT" in t or "BOOL" in t:
        return "int"
    if any(k in t for k in ("REAL", "FLOA", "DOUB", "NUM", "DEC")):
        return "real"
    return "text"


def sample_values(db_path: str, tables: list[Table]) -> dict[tuple[str, str], list]:
    """Up to MAX_SAMPLED_VALUES distinct non-null values per column from the original database."""
    conn = _connect_read_only(db_path)
    out: dict[tuple[str, str], list] = {}
    try:
        for t in tables:
            for c in t.columns:
                try:
                    rows = conn.execute(
                        f"SELECT DISTINCT {_q(c.name)} FROM {_q(t.name)} WHERE {_q(c.name)} IS NOT NULL "
                        f"LIMIT {MAX_SAMPLED_VALUES}").fetchall()
                except sqlite3.Error:
                    rows = []
                out[(t.name, c.name)] = [r[0] for r in rows]
        return out
    finally:
        conn.close()


def _table_order(tables: list[Table]) -> list[Table]:
    by_name = {t.name.lower(): t for t in tables}
    graph = {t.name.lower(): {p.lower() for _, p, _ in t.fks if p.lower() in by_name and p.lower() != t.name.lower()}
             for t in tables}
    try:
        order = list(TopologicalSorter(graph).static_order())
    except CycleError:
        order = list(graph)
    return [by_name[n] for n in order]


def _literal_pool(gold_literals: list) -> dict[str, list]:
    nums = [v for v in gold_literals if isinstance(v, (int, float))]
    texts = [v for v in gold_literals if isinstance(v, str)]
    boundary = [v + d for v in nums for d in (-1, 0, 1)]
    return {"int": [int(v) for v in boundary], "real": boundary, "text": texts}


def _random_value(kind: str, rng: random.Random) -> object:
    if kind == "int":
        return rng.randint(-5, 120)
    if kind == "real":
        return round(rng.uniform(-5, 1000), 2)
    return rng.choice(["a", "b", "x", "foo", "Bar", "", "zz top"]) + str(rng.randint(0, 9))


class _Builder:
    def __init__(self, tables: list[Table], originals: dict, gold_literals: list, rng: random.Random):
        self.tables, self.originals, self.rng = tables, originals, rng
        self.lit = _literal_pool(gold_literals)
        self.rows: dict[str, list[dict]] = {}

    def value(self, table: Table, col: Column) -> object:
        kind, rng = _kind(col.decl_type), self.rng
        if not col.not_null and not col.pk and rng.random() < NULL_PROB:
            return None
        pools = [self.originals.get((table.name, col.name)) or [], self.lit[kind]]
        pool = rng.choice([p for p in pools if p] or [[]])
        if pool and rng.random() < 0.85:
            return rng.choice(pool)
        return _random_value(kind, rng)

    def fk_value(self, parent: str, parent_col: str, col: Column) -> object:
        parent_rows = self.rows.get(parent.lower(), [])
        keys = [r.get(parent_col) for r in parent_rows if r.get(parent_col) is not None] if parent_col else []
        if not keys and parent_rows:
            keys = [next(iter(r.values())) for r in parent_rows]
        if not keys or (not col.not_null and self.rng.random() < NULL_PROB / 3):
            return None if not col.not_null else self.rng.randint(1, 5)
        return self.rng.choice(keys)

    def build_table(self, table: Table) -> list[dict]:
        n = 0 if self.rng.random() < EMPTY_TABLE_PROB else self.rng.randint(1, MAX_ROWS_PER_TABLE)
        fk_map = {c.lower(): (p, pc) for c, p, pc in table.fks}
        rows: list[dict] = []
        seen: dict[tuple[str, ...], set] = {u: set() for u in table.unique_sets}
        for _ in range(n * 4):  # bounded retries when a candidate row breaks a unique constraint
            if len(rows) >= n:
                break
            use_duplicate = rows and self.rng.random() < DUP_PROB
            row = self._duplicate_row(table, rows, fk_map) if use_duplicate else self._new_row(table, fk_map)
            keys = {u: tuple(row[c] for c in u) for u in table.unique_sets}
            if _breaks_unique(table, keys, seen):
                continue
            for u, k in keys.items():
                seen[u].add(k)
            rows.append(row)
        self.rows[table.name.lower()] = rows
        return rows

    def _new_row(self, table: Table, fk_map: dict) -> dict:
        return {c.name: self._fresh(table, c, fk_map) for c in table.columns}

    def _duplicate_row(self, table: Table, rows: list[dict], fk_map: dict) -> dict:
        """Copy an existing row, refreshing only columns under a unique constraint."""
        row = dict(self.rng.choice(rows))
        for c in table.columns:
            if any(c.name in u for u in table.unique_sets):
                row[c.name] = self._fresh(table, c, fk_map)
        return row

    def _fresh(self, table: Table, col: Column, fk_map: dict) -> object:
        if col.name.lower() in fk_map:
            parent, parent_col = fk_map[col.name.lower()]
            return self.fk_value(parent, parent_col, col)
        if col.pk and _kind(col.decl_type) == "int" and self.rng.random() < 0.5:
            return self.rng.randint(1, 30)
        return self.value(table, col)


def _is_pk(table: Table, cols: tuple[str, ...]) -> bool:
    return all(c.pk for c in table.columns if c.name in cols)


def _breaks_unique(table: Table, keys: dict[tuple[str, ...], tuple], seen: dict[tuple[str, ...], set]) -> bool:
    """True if the row repeats a unique key, or has NULL in a single-column primary key."""
    has_null_pk = any(None in k and len(u) == 1 and _is_pk(table, u) for u, k in keys.items())
    return has_null_pk or any(k in seen[u] for u, k in keys.items())


def generate_db(src_db: str, dst_db: str, seed: int, gold_literals: list | None = None,
                tables: list[Table] | None = None, originals: dict | None = None) -> str:
    """Copy the schema of src_db into dst_db and fill it with small random data."""
    tables = tables or read_schema(src_db)
    originals = originals if originals is not None else sample_values(src_db, tables)
    rng = random.Random(seed)
    builder = _Builder(tables, originals, gold_literals or [], rng)
    Path(dst_db).parent.mkdir(parents=True, exist_ok=True)
    Path(dst_db).unlink(missing_ok=True)
    src = sqlite3.connect(f"file:{src_db}?mode=ro", uri=True)
    ddl = [r[0] for r in src.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")]
    src.close()
    dst = sqlite3.connect(dst_db)
    try:
        for stmt in ddl:
            dst.execute(stmt)
        for table in _table_order(tables):
            rows = builder.build_table(table)
            if rows:
                cols = [c.name for c in table.columns]
                dst.executemany(
                    f"INSERT OR IGNORE INTO {_q(table.name)} ({', '.join(map(_q, cols))}) VALUES ({', '.join('?' * len(cols))})",
                    [tuple(r[c] for c in cols) for r in rows])
        dst.commit()
    finally:
        dst.close()
    return dst_db


def copy_original(src_db: str, dst_db: str) -> str:
    Path(dst_db).parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src_db, dst_db)
    return dst_db
