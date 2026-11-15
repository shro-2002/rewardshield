"""Route recorded evaluation trajectories through AuditKIT's agent_eval and write toolkit metrics.

Per model: task success (test-suite oracle labels, run as the AuditKIT case oracle), tool-call
accuracy (AuditKIT tool_call_validity plus execution-based rates from the recorded tool results),
model episode time (batch-16 throughput logs; batch-1 latency only from lat_*.jsonl when given) and
verifier CPU latency (single-1 and targeted-4 re-run here). Missing timings are reported as null.
uv run python scripts/auditkit_eval.py            # defaults: E00/E01/E04/E05 on dev-B
uv run python scripts/auditkit_eval.py --model E07=runs/E07/out/E07_devB.jsonl --latency E07=runs/E07/out/lat_E07.jsonl
"""

import argparse
import json
import platform
import re
import statistics
import sys
import tempfile
import time
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from auditkit.agent_eval import AgentCase, AgentEvalRunner, AgentEvalSpec, CustomPredicate  # noqa: E402
from auditkit.agent_eval import episode_from_openai_messages  # noqa: E402

from rewardshield.agent import final_sql, make_run_sql  # noqa: E402
from rewardshield.data import load_split  # noqa: E402
from rewardshield.verifiers import build_suite, verify  # noqa: E402

OUT = "runs/E04/out"
DEFAULT_MODELS = {m: f"{OUT}/{m}_devB.jsonl" for m in ("E00", "E01", "E04", "E05")}
DEFAULT_THROUGHPUT = {"E00": f"{OUT}/v1b.log", "E01": f"{OUT}/v0b.log", "E04": f"{OUT}/v0a.log", "E05": f"{OUT}/v1a.log"}
LABELS = {"E00": "E00 base", "E01": "E01 warm start", "E04": "E04 single-1 arm", "E05": "E05 targeted-4 arm",
          "E07": "E07 gold-trajectory control"}
SCORERS = ["tool_call_validity", "redundant_tool_calls", "agent_loop_detection"]
ATTEMPT_RE = re.compile(r"tool_name|sql_command")


def _run_sql_schema() -> dict:
    from transformers.utils import get_json_schema
    return get_json_schema(make_run_sql(":memory:"))


def unfold(messages: list[dict]) -> list[dict]:
    """Recorded Tiny Aya turns -> OpenAI messages: folded "Tool result for run_sql: ..." user turns become
    "tool" turns paired to their call by id. The system prompt (schema + tool text) is dropped."""
    out, pending = [], []
    for m in messages:
        if m["role"] == "system":
            continue
        if m["role"] == "assistant" and m.get("tool_calls"):
            calls = [{**c, "id": c.get("id") or f"call_{len(out)}_{j}"} for j, c in enumerate(m["tool_calls"])]
            out.append({**m, "tool_calls": calls})
            pending = [c["id"] for c in calls]
        elif m["role"] == "user" and pending and m["content"].startswith("Tool result for "):
            parts = m["content"].split("\nTool result for ")  # parallel calls share one folded turn
            for cid, part in zip(pending, parts):
                body = part.removeprefix("Tool result for ").split(": ", 1)[-1]
                out.append({"role": "tool", "tool_call_id": cid, "content": body.split("\nUse this result")[0]})
            pending = []
        else:
            out.append(m)
    return out


def execution_stats(records: list[dict]) -> dict:
    """Tool-call accuracy from the recorded tool results (what the agent saw at the time)."""
    n_calls = n_ok = clean = parsed_all = with_call = 0
    for rec in records:
        msgs = unfold(rec["messages"])
        results = [m["content"] for m in msgs if m["role"] == "tool"]
        calls = sum(len(m["tool_calls"]) for m in msgs if m["role"] == "assistant" and m.get("tool_calls"))
        ok = sum(1 for r in results if "'error'" not in r[:200] and '"error"' not in r[:200])
        unparsed = any(m["role"] == "assistant" and not m.get("tool_calls") and ATTEMPT_RE.search(m.get("content") or "")
                       for m in msgs)
        n_calls, n_ok = n_calls + calls, n_ok + ok
        with_call += calls > 0
        parsed_all += not unparsed
        clean += calls > 0 and not unparsed and ok == calls
    n = len(records)
    return {"episodes": n, "parsed_calls": n_calls, "executed_ok_calls": n_ok,
            "call_execution_rate": _r(n_ok / n_calls) if n_calls else None,
            "episode_all_parsed_rate": _r(parsed_all / n), "episode_with_call_rate": _r(with_call / n),
            "episode_clean_rate": _r(clean / n)}


def throughput(log_path: str | None) -> dict | None:
    """Last JSON line of a Kaggle rollout log: {"rollouts", "seconds", "rollouts_per_min"} at batch 16."""
    if not log_path or not Path(log_path).exists():
        return None
    for line in reversed(Path(log_path).read_text().splitlines()):
        if line.startswith("{"):
            d = json.loads(line)
            return {**d, "seconds_per_episode": _r(d["seconds"] / d["rollouts"], 3), "batch": 16, "source": log_path,
                    "label": "amortised batch-16 throughput (T4), not per-episode latency"}
    return None


def batch1_latency(path: str | None) -> dict | None:
    if not path or not Path(path).exists():
        return None
    secs = [json.loads(line)["seconds"] for line in open(path) if line.strip()]
    return {"n": len(secs), "mean_s": _r(statistics.mean(secs), 3), "median_s": _r(statistics.median(secs), 3),
            "source": path, "label": "measured per-episode wall time at batch 1"}


def verifier_timing(records: list[dict], questions: dict, suites: dict) -> tuple[dict, dict]:
    """Time single-1 and targeted-4 on each episode's final SQL (CPU). Returns (timing, verdicts by case id)."""
    ms = {"single-1": [], "targeted-4": []}
    verdicts = {}
    for rec in records:
        pred, cid = rec.get("final_sql"), _case_id(rec)
        if not pred:
            verdicts[cid] = {"single-1": False, "targeted-4": False}
            continue
        verdicts[cid] = {}
        for key, (mode, k) in {"single-1": ("single", 1), "targeted-4": ("targeted", 4)}.items():
            start = time.perf_counter()
            v = verify(suites[rec["qid"]], pred, mode, k)
            ms[key].append((time.perf_counter() - start) * 1000)
            verdicts[cid][key] = v.accept
    timing = {key: {"n": len(v), "median_ms": _r(statistics.median(v), 3), "mean_ms": _r(statistics.mean(v), 3)}
              for key, v in ms.items() if v}
    return timing, verdicts


def auditkit_run(records: list[dict], questions: dict, oracle: dict | None, verdicts: dict,
                 latency: dict | None, schema: dict):
    """One AgentEvalSpec in recorded mode: the oracle label is the case outcome, the targeted-4
    verdict is the episode's source verdict (AuditKIT records where it disagrees with the oracle)."""
    lat = {}
    if latency:
        lat = {(r.get("qid"), r.get("sample", 0)): r["seconds"] for r in map(json.loads, open(latency["source"]))}
    cases, episodes = [], []
    for rec in records:
        cid, key = _case_id(rec), (rec["qid"], rec["sample"])
        ep = episode_from_openai_messages(unfold(rec["messages"]), case_id=cid, source_id=cid,
                                          final_answer=final_sql(rec["messages"]) or "")
        ep.source_verdict, ep.source_scores = verdicts[cid]["targeted-4"], verdicts[cid]
        if key in lat:
            ep.counters["latency_ms"] = lat[key] * 1000
        outcome = None
        if oracle is not None and key in oracle:
            outcome = CustomPredicate(_oracle_says, version="test-suite-oracle-labels-v1", name="oracle_label")
        cases.append(AgentCase(id=cid, task=questions[rec["qid"]]["question"], category="spider-dev-B",
                               allowed_tools=[schema], outcome=outcome,
                               metadata={"oracle": oracle.get(key) if oracle else None}))
        episodes.append(ep)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return AgentEvalRunner().run(AgentEvalSpec(cases=cases, episodes=episodes, mode="recorded",
                                                   scorers=SCORERS, name="rewardshield-devB"))


def _oracle_says(episode, case) -> bool:
    return bool(case.metadata["oracle"])


def summarise(result) -> dict:
    rows = result.rows
    verdicts = [r.outcome.get("verdict") for r in rows]
    decided = verdicts.count("success") + verdicts.count("failure")
    diag = {s: [r.diagnostics[s]["value"] for r in rows if s in r.diagnostics] for s in SCORERS}
    calls = [r.diagnostics["tool_call_validity"]["metadata"] for r in rows if "tool_call_validity" in r.diagnostics]
    dis = [r.disagreement["source_vs_oracle"] for r in rows if "source_vs_oracle" in (r.disagreement or {})]
    return {
        "cases": len(rows), "success": verdicts.count("success"), "decided": decided,
        "task_success_rate": _r(verdicts.count("success") / decided) if decided else None,
        "tool_call_validity_mean": _r(statistics.mean(diag["tool_call_validity"])) if diag["tool_call_validity"] else None,
        "tool_call_validity_eligible": len(diag["tool_call_validity"]),
        "invalid_calls": sum(c["n_invalid"] for c in calls), "validated_calls": sum(c["n_calls"] for c in calls),
        "redundant_tool_calls_mean": _r(statistics.mean(diag["redundant_tool_calls"])) if diag["redundant_tool_calls"] else None,
        "loop_free_rate": _r(statistics.mean(diag["agent_loop_detection"])) if diag["agent_loop_detection"] else None,
        "targeted4_vs_oracle": {"accepts_oracle_wrong": sum(1 for d in dis if d["source_verdict"] == "success"),
                                "rejects_oracle_correct": sum(1 for d in dis if d["source_verdict"] == "failure")},
        "statuses": sorted({r.status for r in rows}),
        "auditkit_summary": result.summary(),
    }


def _case_id(rec: dict) -> str:
    return f"{rec['qid']}#{rec.get('sample', 0)}"


def _r(x: float, nd: int = 4) -> float:
    return round(x, nd)


def _pairs(items: list[str]) -> dict:
    return dict(item.split("=", 1) for item in items)


def evaluate(models: dict, questions: dict, throughput_logs: dict, latency_files: dict, cache: str) -> dict:
    schema, suites, out = _run_sql_schema(), {}, {}
    build_s = []
    for name, path in models.items():
        records = [json.loads(line) for line in open(path)]
        oracle_path = Path(path).with_name(Path(path).stem + "_oracle.jsonl")
        oracle = ({(o["qid"], o["sample"]): o["oracle"] for o in map(json.loads, open(oracle_path))}
                  if oracle_path.exists() else None)
        for qid in {r["qid"] for r in records} - suites.keys():
            q = questions[qid]
            suites[qid] = build_suite(qid, q["gold"], q["db_path"], cache)
            build_s.append(suites[qid].build_seconds)
        timing, verdicts = verifier_timing(records, questions, suites)
        latency = batch1_latency(latency_files.get(name))
        summary = summarise(auditkit_run(records, questions, oracle, verdicts, latency, schema))
        out[name] = {"label": LABELS.get(name, name), "records": path,
                     "oracle": str(oracle_path) if oracle else None, **summary,
                     "execution": execution_stats(records),
                     "episode_time": {"batch16_throughput": throughput(throughput_logs.get(name)), "batch1_latency": latency},
                     "verifier_cpu_ms_per_episode": timing}
    meta = {"suite_build_s_per_question": {"n": len(build_s), "median": _r(statistics.median(build_s), 3),
                                          "mean": _r(statistics.mean(build_s), 3)} if build_s else None,
            "cpu": f"{platform.machine()} {platform.platform()}", "python": platform.python_version()}
    return {"models": out, "meta": meta}


def _fmt(x, pct: bool = False, nd: int = 1) -> str:
    if x is None:
        return "missing"
    return f"{100 * x:.{nd}f}%" if pct else f"{x:.{nd}f}"


def _pct(num: int, den: int) -> str:
    return f"{100 * num / den:.1f}%" if den else "missing"


def write_markdown(report: dict, path: str) -> None:
    m, meta = report["models"], report["meta"]
    e00 = m.get("E00", {})
    base = e00["success"] / e00["decided"] if e00.get("decided") else None
    lines = ["# Toolkit metrics (AuditKIT agent_eval + RewardShield verifiers)", "",
             "Generated by `scripts/auditkit_eval.py`. Greedy evaluation episodes on dev-B (379 questions each). "
             "Before = E00 base; after = E04 / E05 (E01 and E07 for reference).", "",
             "| Model | Task success | Δ vs E00 | AuditKIT tool_call_validity | Call execution rate | Clean-episode rate "
             "| Episode time, batch-16 amortised (s) | Episode latency, batch 1 (s) | Verifier ms/episode single-1 / targeted-4 |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, r in m.items():
        ex, et, vt = r["execution"], r["episode_time"], r["verifier_cpu_ms_per_episode"]
        tp, b1 = et["batch16_throughput"], et["batch1_latency"]
        delta = (f"{100 * (r['success'] / r['decided'] - base):+.1f} pts"
                 if base is not None and r["task_success_rate"] is not None and name != "E00" else "–")
        lines.append(
            f"| {r['label']} | {_pct(r['success'], r['decided'])} ({r['success']}/{r['decided']}) | {delta} | "
            f"{_fmt(r['tool_call_validity_mean'], True)} | {_fmt(ex['call_execution_rate'], True)} "
            f"({ex['executed_ok_calls']}/{ex['parsed_calls']}) | {_fmt(ex['episode_clean_rate'], True)} | "
            f"{_fmt(tp and tp['seconds_per_episode'], nd=2)} | {_fmt(b1 and b1['mean_s'], nd=2)} | "
            f"{_fmt(vt.get('single-1', {}).get('median_ms'), nd=2)} / {_fmt(vt.get('targeted-4', {}).get('median_ms'), nd=2)} |")
    sb = meta["suite_build_s_per_question"]
    lines += ["", "## Definitions", "",
              "- **Task success**: share of episodes the test-suite oracle labels correct, taken from "
              "`runs/E04/out/<model>_devB_oracle.jsonl`. The label is the AuditKIT case outcome "
              "(`CustomPredicate`, version `test-suite-oracle-labels-v1`) and is not recomputed here.",
              "- **AuditKIT tool_call_validity**: AuditKIT's metric, mean over episodes with at least one parsed call: "
              "share of calls valid against the `run_sql` JSON schema (tool exists, `sql_command` present and a string). "
              "It does not run the SQL.",
              "- **Call execution rate**: of all parsed `run_sql` calls, the share whose recorded tool result is not an error.",
              "- **Clean-episode rate** (episode-level tool-call accuracy): share of all episodes that made at least one "
              "parsed call, had no unparsed call attempt (an assistant turn mentioning `tool_name`/`sql_command` that "
              "AgentTune's parser did not accept), and whose every call executed without error.",
              "- **Episode time, batch-16 amortised**: wall seconds / episodes from the Kaggle T4 rollout log "
              "(`runs/E04/out/v*.log`, last JSON line). Throughput, not per-episode latency.",
              "- **Episode latency, batch 1**: mean of `seconds` in `lat_<model>.jsonl` when given; `missing` otherwise "
              "(never imputed from throughput).",
              f"- **Verifier ms/episode**: median CPU time of `verify()` on the episode's final SQL, re-run here "
              f"({meta['cpu']}); suites built once per question (median {_fmt(sb and sb['median'], nd=3)} s/question, "
              "not included). Episodes with no committed SQL are not timed.", "",
              "## Other AuditKIT diagnostics", "",
              "| Model | redundant_tool_calls (mean, lower is better) | agent_loop_detection (loop-free share) "
              "| targeted-4 accepts oracle-wrong | targeted-4 rejects oracle-correct | Statuses |", "|---|---|---|---|---|---|"]
    for r in m.values():
        tv = r["targeted4_vs_oracle"]
        lines.append(f"| {r['label']} | {_fmt(r['redundant_tool_calls_mean'], nd=3)} | {_fmt(r['loop_free_rate'], True)} | "
                     f"{tv['accepts_oracle_wrong']} | {tv['rejects_oracle_correct']} | {', '.join(r['statuses'])} |")
    lines += ["", "The targeted-4 columns come from AuditKIT's source-vs-oracle disagreement record (the verifier "
              "verdict is attached as the episode's `source_verdict`; the oracle wins the headline).", "",
              "## AuditKIT run summaries", ""]
    for r in m.values():
        lines += [f"**{r['label']}**", "", "```", r["auditkit_summary"], "```", ""]
    Path(path).write_text("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", action="append", default=[], help="NAME=records.jsonl (added to the defaults)")
    ap.add_argument("--throughput", action="append", default=[], help="NAME=v*.log")
    ap.add_argument("--latency", action="append", default=[], help="NAME=lat_*.jsonl (batch-1 seconds per episode)")
    ap.add_argument("--split", default="data/splits/devB.jsonl")
    ap.add_argument("--cache", default=None, help="suite cache (default: a temp dir; never data/cache for dev-B)")
    ap.add_argument("--out", default="reports/toolkit_metrics")
    args = ap.parse_args()
    models = {**DEFAULT_MODELS, **_pairs(args.model)}
    cache = args.cache or tempfile.mkdtemp(prefix="rewardshield-devB-suites-")
    questions = {q["qid"]: q for q in load_split(args.split)}
    report = evaluate(models, questions, {**DEFAULT_THROUGHPUT, **_pairs(args.throughput)}, _pairs(args.latency), cache)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out + ".json").write_text(json.dumps(report, indent=2))
    write_markdown(report, args.out + ".md")
    print(Path(args.out + ".md").read_text().split("## Definitions")[0])


if __name__ == "__main__":
    main()
