"""SQL agent prompt, sandboxed tool, trajectory parsing and gold trajectories.

The rollout format is AgentTune's Tiny Aya fallback (the Tiny Aya chat template does not render
tools): tool schemas are appended to the system prompt, the model calls tools with a JSON list
and tool results come back as a user turn "Tool result for run_sql: ...". Gold SFT trajectories
are written in exactly that format so training and rollout prompts match.
The evaluated answer is the last successfully executed SQL, as in AgentTune's result_match_reward.
"""

from __future__ import annotations

import json
import sqlite3
from functools import lru_cache

from .sqlexec import execute

MAX_TOOL_ROWS = 10
INSTRUCTIONS = (
    "Answer the question by running SQL with the run_sql tool. You may run several queries. "
    "The last query that runs without error is taken as your final answer, so finish with the "
    "query that answers the question exactly. Then reply in one short sentence."
)
# Copied from agenttune.agentic.rollout_engines.rollout_factory (1.1.5); asserted in tests.
TOOL_RESULT_FORMAT = "Tool result for {name}: {content}\nUse this result to answer the original question."


@lru_cache(maxsize=512)
def schema_text(db_path: str) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        ddl = [r[0].strip() for r in conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%'")]
    finally:
        conn.close()
    return "\n".join(ddl)


def system_prompt(db_path: str) -> str:
    return f"You are a SQL agent for a SQLite database with this schema:\n{schema_text(db_path)}\n\n{INSTRUCTIONS}"


def make_run_sql(db_path: str):
    """A tool bound to one database. Read-only, time- and size-limited (see sqlexec.execute)."""

    def run_sql(sql_command: str) -> list:
        """Run a read-only SQLite query on the database and return up to 10 rows.

        Args:
            sql_command: The SQLite query to execute.
        """
        res = execute(db_path, sql_command)
        if not res.ok:
            return [{"error": res.error}]
        return [list(r) for r in res.rows[:MAX_TOOL_ROWS]]

    return run_sql


def full_system_prompt(db_path: str) -> str:
    """System prompt exactly as AgentTune builds it for a template that ignores tools."""
    from agenttune.agentic.rollout_engines.rollout_factory import DEFAULT_TOOLS_FALLBACK_PROMPT
    from transformers.utils import get_json_schema

    schemas = [get_json_schema(make_run_sql(db_path))]
    fallback = DEFAULT_TOOLS_FALLBACK_PROMPT.format(tools=json.dumps(schemas, indent=2))
    return f"{system_prompt(db_path)}\n\n{fallback}"


def tool_call_text(sql: str) -> str:
    return json.dumps([{"tool_name": "run_sql", "parameters": {"sql_command": sql}}])


def gold_trajectory(question: str, gold_sql: str, db_path: str) -> list[dict]:
    rows = make_run_sql(db_path)(gold_sql)
    return [
        {"role": "system", "content": full_system_prompt(db_path)},
        {"role": "user", "content": question},
        {"role": "assistant", "content": tool_call_text(gold_sql)},
        {"role": "user", "content": TOOL_RESULT_FORMAT.format(name="run_sql", content=rows)},
        {"role": "assistant", "content": f"The query returned: {rows[:3]}"},
    ]


def _sql_of(call: dict) -> str:
    args = (call.get("function") or {}).get("arguments") or {}
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            return ""
    return str(args.get("sql_command", "")) if isinstance(args, dict) else ""


def _is_error_result(content: str) -> bool:
    return "'error'" in content[:200] or '"error"' in content[:200]


def tool_calls(conversation: list[dict]) -> list[tuple[str, str | None]]:
    """(sql, result text) for every run_sql call in order; result is None if no reply followed."""
    out: list[tuple[str, str | None]] = []
    for i, msg in enumerate(conversation):
        if msg.get("role") != "assistant":
            continue
        for call in msg.get("tool_calls") or []:
            nxt = conversation[i + 1] if i + 1 < len(conversation) else {}
            result = nxt.get("content") if nxt.get("role") in ("tool", "user") else None
            out.append((_sql_of(call), result))
    return out


def final_sql(conversation: list[dict]) -> str | None:
    """Last SQL whose tool result was not an error (the agent's committed answer)."""
    for sql, result in reversed(tool_calls(conversation)):
        if sql and result is not None and not _is_error_result(str(result)):
            return sql
    return None
