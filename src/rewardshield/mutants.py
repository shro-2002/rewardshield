"""One-change mutants of a gold SQL query, used only to pick distinguishing databases.

Operators follow common SQL mutation testing practice (Tuya et al. 2006; Zhong et al. 2020):
comparison operators, numeric constants +/-1, dropped WHERE/HAVING conjuncts, AND/OR swap,
aggregate swaps, COUNT/DISTINCT variants, join type, sort direction, LIMIT removal, GROUP BY
column removal and same-table column swaps. Mutants never reach the model; they only decide
which generated databases a targeted verifier keeps.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import sqlglot
from sqlglot import exp

MAX_MUTANTS = 80
_CMP_SWAPS = {exp.EQ: [exp.NEQ, exp.GT, exp.LT], exp.NEQ: [exp.EQ], exp.GT: [exp.GTE, exp.LT, exp.EQ],
              exp.GTE: [exp.GT, exp.LTE], exp.LT: [exp.LTE, exp.GT, exp.EQ], exp.LTE: [exp.LT, exp.GTE]}
_AGG_SWAPS = {exp.Count: [exp.Sum], exp.Sum: [exp.Avg, exp.Count, exp.Max], exp.Avg: [exp.Sum, exp.Max, exp.Min],
              exp.Max: [exp.Min, exp.Avg], exp.Min: [exp.Max, exp.Avg]}


def _variants(tree: exp.Expression, select: Callable[[exp.Expression], bool],
              rewrite: Callable[[exp.Expression], list[exp.Expression | None]]) -> Iterator[exp.Expression]:
    """For each node matching select, yield a copy of tree with that one node rewritten."""
    targets = [n for n in tree.walk() if select(n)]
    for i in range(len(targets)):
        probe = tree.copy()
        node = [n for n in probe.walk() if select(n)][i]
        for replacement in rewrite(node):
            mutated = probe.copy()
            target = [n for n in mutated.walk() if select(n)][i]
            if replacement is None:
                _drop(target)
            else:
                target.replace(replacement.copy())
            yield mutated


def _drop(node: exp.Expression) -> None:
    """Remove a conjunct from an AND, or the whole clause if it is the only condition."""
    parent = node.parent
    if isinstance(parent, exp.And):
        other = parent.right if node is parent.left else parent.left
        parent.replace(other.copy())
    elif isinstance(parent, (exp.Where, exp.Having)):
        parent.pop()
    else:
        node.pop()


def _cmp(node: exp.Expression) -> list[exp.Expression]:
    return [cls(this=node.this.copy(), expression=node.expression.copy()) for cls in _CMP_SWAPS[type(node)]]


def _num(node: exp.Literal) -> list[exp.Expression]:
    val = float(node.this)
    return [exp.Literal.number(int(v) if float(v).is_integer() else v) for v in (val - 1, val + 1)]


def _agg(node: exp.Expression) -> list[exp.Expression]:
    return [cls(this=node.this.copy()) for cls in _AGG_SWAPS[type(node)]]


def _count(node: exp.Count) -> list[exp.Expression]:
    inner = node.this
    if isinstance(inner, exp.Distinct):
        return [exp.Count(this=inner.expressions[0].copy())] if inner.expressions else []
    if isinstance(inner, exp.Star) or inner is None:
        return []
    return [exp.Count(this=exp.Star()), exp.Count(this=exp.Distinct(expressions=[inner.copy()]))]


def _distinct(node: exp.Select) -> list[exp.Expression]:
    toggled = node.copy()
    toggled.set("distinct", None if node.args.get("distinct") else exp.Distinct())
    return [toggled]


def _join(node: exp.Join) -> list[exp.Expression]:
    flipped = node.copy()
    flipped.set("side", None if node.side else "LEFT")
    flipped.set("kind", None)
    return [flipped]


def _order(node: exp.Ordered) -> list[exp.Expression]:
    flipped = node.copy()
    flipped.set("desc", not node.args.get("desc"))
    return [flipped]


def _andor(node: exp.Expression) -> list[exp.Expression]:
    cls = exp.Or if isinstance(node, exp.And) else exp.And
    return [cls(this=node.this.copy(), expression=node.expression.copy())]


def _in_where_or_having(node: exp.Expression) -> bool:
    return node.find_ancestor(exp.Where, exp.Having) is not None


def _is_conjunct(node: exp.Expression) -> bool:
    return isinstance(node, exp.Predicate) and _in_where_or_having(node) and not isinstance(node.parent, exp.Predicate)


def _column_swaps(tree: exp.Expression, columns_by_table: dict[str, list[str]]) -> Iterator[exp.Expression]:
    names = {c.lower() for cols in columns_by_table.values() for c in cols}
    for i, col in enumerate(list(tree.find_all(exp.Column))):
        same_table = next((cols for cols in columns_by_table.values() if col.name.lower() in {c.lower() for c in cols}), [])
        for other in [c for c in same_table if c.lower() != col.name.lower() and c.lower() in names][:2]:
            mutated = tree.copy()
            target = list(mutated.find_all(exp.Column))[i]
            target.set("this", exp.to_identifier(other))
            yield mutated


def generate_mutants(gold_sql: str, columns_by_table: dict[str, list[str]] | None = None) -> list[str]:
    """Distinct, parseable one-change mutants of gold_sql (gold itself excluded)."""
    try:
        tree = sqlglot.parse_one(gold_sql, read="sqlite")
    except sqlglot.errors.ParseError:
        return []
    gens = [
        _variants(tree, lambda n: type(n) in _CMP_SWAPS, _cmp),
        _variants(tree, lambda n: isinstance(n, exp.Literal) and not n.is_string, _num),
        _variants(tree, _is_conjunct, lambda n: [None]),
        _variants(tree, lambda n: isinstance(n, (exp.And, exp.Or)) and _in_where_or_having(n), _andor),
        _variants(tree, lambda n: type(n) in _AGG_SWAPS and not isinstance(n, exp.Count), _agg),
        _variants(tree, lambda n: isinstance(n, exp.Count), _count),
        _variants(tree, lambda n: isinstance(n, exp.Select), _distinct),
        _variants(tree, lambda n: isinstance(n, exp.Join), _join),
        _variants(tree, lambda n: isinstance(n, exp.Ordered), _order),
        _variants(tree, lambda n: isinstance(n, exp.Limit), lambda n: [None]),
        _variants(tree, lambda n: isinstance(n, exp.Column) and isinstance(n.parent, exp.Group), lambda n: [None]),
    ]
    if columns_by_table:
        gens.append(_column_swaps(tree, columns_by_table))
    gold_norm = tree.sql(dialect="sqlite")
    out: list[str] = []
    seen = {gold_norm}
    for gen in gens:
        try:
            for mutant in gen:
                sql = mutant.sql(dialect="sqlite")
                if sql not in seen:
                    seen.add(sql)
                    out.append(sql)
                if len(out) >= MAX_MUTANTS:
                    return out
        except (sqlglot.errors.SqlglotError, ValueError, AttributeError, IndexError, TypeError):
            continue  # an operator that cannot apply to this tree shape yields nothing
    return out
