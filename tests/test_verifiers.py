import sqlite3

import pytest

from rewardshield.mutants import generate_mutants
from rewardshield.sqlexec import execute, has_top_level_order, literals, results_match
from rewardshield.verifiers import build_suite, verify

# Original database is deliberately "unlucky": each order has one item and every account is in Peru,
# so several wrong queries coincide with the gold on it (the ReViSQL failure pattern).
SCHEMA = """
CREATE TABLE accounts (id INTEGER PRIMARY KEY, owner TEXT NOT NULL, country TEXT);
CREATE TABLE orders (order_id INTEGER PRIMARY KEY, account_id INTEGER REFERENCES accounts(id), status TEXT);
CREATE TABLE items (item_id INTEGER PRIMARY KEY, order_id INTEGER REFERENCES orders(order_id), price REAL NOT NULL);
INSERT INTO accounts VALUES (1,'Ana','Peru'),(2,'Luz','Peru');
INSERT INTO orders VALUES (10,1,'paid'),(11,1,'paid'),(12,2,'paid');
INSERT INTO items VALUES (100,10,20.0),(101,11,40.0),(102,12,15.0);
"""


@pytest.fixture()
def db(tmp_path):
    path = tmp_path / "orig.sqlite"
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)
    return str(path)


@pytest.fixture()
def suite_factory(db, tmp_path):
    def make(gold, qid="q"):
        return build_suite(qid, gold, db, str(tmp_path / "cache"))
    return make


GOLD_AVG_ORDER = ("SELECT AVG(t) FROM (SELECT o.order_id, SUM(i.price) AS t FROM orders o "
                  "JOIN items i ON o.order_id = i.order_id WHERE o.account_id = 1 GROUP BY o.order_id)")

KNOWN_WRONG = [
    (GOLD_AVG_ORDER, "SELECT AVG(i.price) FROM orders o JOIN items i ON o.order_id = i.order_id WHERE o.account_id = 1"),
    ("SELECT owner FROM accounts WHERE country = 'Peru'", "SELECT owner FROM accounts"),
    ("SELECT COUNT(*) FROM orders WHERE status = 'paid'", "SELECT COUNT(*) FROM orders"),
    # owner is not unique: the IN form keeps two accounts that share a name, DISTINCT collapses them.
    ("SELECT DISTINCT a.owner FROM accounts a JOIN orders o ON a.id = o.account_id",
     "SELECT owner FROM accounts WHERE id IN (SELECT account_id FROM orders)"),
]

EQUIVALENT = [
    ("SELECT COUNT(*) FROM accounts", "SELECT COUNT(id) FROM accounts"),
    ("SELECT owner FROM accounts WHERE id >= 1 AND id <= 2", "SELECT owner FROM accounts WHERE id BETWEEN 1 AND 2"),
    ("SELECT owner, country FROM accounts", "SELECT country, owner FROM accounts"),
    ("SELECT a.owner FROM accounts AS a WHERE a.country = 'Peru' AND a.id > 0",
     "SELECT owner FROM accounts WHERE id > 0 AND country = 'Peru'"),
    ("SELECT owner FROM accounts WHERE country <> 'Chile'", "SELECT owner FROM accounts WHERE country != 'Chile'"),
    ("SELECT DISTINCT a.owner FROM accounts a JOIN orders o ON a.id = o.account_id",
     "SELECT a.owner FROM accounts a JOIN orders o ON a.id = o.account_id GROUP BY a.owner"),
]


def test_execute_is_read_only(db):
    assert not execute(db, "INSERT INTO accounts VALUES (9,'x','y')").ok
    assert not execute(db, "ATTACH DATABASE ':memory:' AS other").ok
    assert not execute(db, "PRAGMA writable_schema = 1").ok


def test_execute_times_out(db):
    slow = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM c) SELECT COUNT(*) FROM c"
    res = execute(db, slow, timeout_s=0.2)
    assert not res.ok


def test_results_match_semantics():
    assert results_match(((1,), (1,), (2,)), ((2,), (1,), (1,)), ordered=False)
    assert not results_match(((1,), (1,), (2,)), ((1,), (2,)), ordered=False)  # duplicates count
    assert results_match(((1, "a"),), (("a", 1),), ordered=False)  # column order ignored
    assert not results_match(((1,), (2,)), ((2,), (1,)), ordered=True)
    assert results_match(((1.0,),), ((1,),), ordered=False)
    assert results_match(((None,),), ((None,),), ordered=False)


def test_helpers():
    assert has_top_level_order("SELECT a FROM t ORDER BY a")
    assert not has_top_level_order("SELECT a FROM (SELECT a FROM t ORDER BY a)")
    assert set(literals("SELECT a FROM t WHERE b = 'x' AND c > 3")) == {"x", 3}


def test_mutants_exclude_gold_and_parse():
    muts = generate_mutants("SELECT COUNT(*) FROM orders WHERE status = 'paid' AND order_id > 10")
    assert muts and all("orders" in m.lower() for m in muts)
    assert "SELECT COUNT(*) FROM orders WHERE status = 'paid' AND order_id > 10" not in muts


@pytest.mark.parametrize("gold, wrong", KNOWN_WRONG)
def test_single_db_accepts_known_wrong_but_targeted_rejects(suite_factory, gold, wrong):
    suite = suite_factory(gold, qid=f"w{abs(hash(wrong)) % 10_000}")
    assert verify(suite, wrong, "single").accept, "fixture must reproduce the single-database false accept"
    assert not verify(suite, wrong, "targeted", k=4).accept


@pytest.mark.parametrize("gold, rewrite", EQUIVALENT)
@pytest.mark.parametrize("mode", ["single", "random", "targeted"])
def test_equivalent_rewrites_accepted(suite_factory, gold, rewrite, mode):
    suite = suite_factory(gold, qid=f"e{abs(hash(rewrite)) % 10_000}")
    assert verify(suite, rewrite, mode, k=4).accept


def test_gold_always_accepts_itself(suite_factory):
    suite = suite_factory(GOLD_AVG_ORDER, qid="self")
    for mode in ("single", "random", "targeted"):
        assert verify(suite, GOLD_AVG_ORDER, mode, k=4).accept


def test_execution_error_is_reject(suite_factory):
    suite = suite_factory("SELECT owner FROM accounts", qid="err")
    verdict = verify(suite, "SELECT nope FROM accounts", "targeted", k=4)
    assert not verdict.accept and "error" in verdict.reason
