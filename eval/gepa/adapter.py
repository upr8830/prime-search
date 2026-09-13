"""GEPA adapter for PRIME (docs/05 §5).

GEPA proposes new texts for `plan.md` and `judge.md` (and `critic.md` when asked). This
adapter runs the real PRIME graph with those texts on SearchBench train and dev records,
scores each run with the bench evaluators, and gives GEPA's reflection step the
evaluator comments plus what the optimized component actually did on the run.

Holdout records are refused here as well as in the runner: docs/05 §5's guardrail is that
optimization never sees them.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from typing import Any

from gepa import EvaluationBatch

from eval.evaluators import composite, feedback_text, score_record
from eval.run_eval import _saved_record
from eval.searchbench.schema import BenchRecord
from prime_search import prompts
from prime_search.agents.graph import run_prime
from prime_search.config import Budget
from prime_search.schemas import RunRecord, RunRequest
from prime_search.workspace import Workspace

__all__ = [
    "COMPONENTS",
    "GEPA_PROJECT",
    "PrimeAdapter",
    "Rollout",
    "candidate_problems",
    "critic_view",
    "judge_view",
    "plan_view",
    "prompt_set_name",
]

GEPA_PROJECT = "prime-search-gepa"
# docs/05 §5's targets: the prompts that shape what gets searched and when to stop.
COMPONENTS = ("plan", "judge", "critic")
MAX_FEEDBACK_CHARS = 4000
_PLACEHOLDER = re.compile(r"\{[a-z_]+\}")

Runner = Callable[..., RunRecord]
Scorer = Callable[[RunRecord | None, BenchRecord], Mapping[str, Any]]


@dataclass
class Rollout:
    """One scored run of one candidate on one record: what GEPA keeps as the output and
    reads back as the trajectory. Strings only, so GEPA's checkpoints stay small."""

    question_id: str
    run_id: str | None
    status: str
    score: float
    composite: float | None
    feedback: str
    plan: str
    judge: str
    critic: str
    usage: str
    error: str | None = None


def prompt_set_name(candidate: Mapping[str, str]) -> str:
    """A stable name per candidate text, so one candidate is one registered set."""
    encoded = json.dumps(dict(sorted(candidate.items())), ensure_ascii=False).encode("utf-8")
    return f"gepa-{hashlib.sha1(encoded).hexdigest()[:10]}"


def candidate_problems(candidate: Mapping[str, str]) -> list[str]:
    """Why a candidate cannot run. A prompt that lost a placeholder of its base text would
    run without that input (the plan without its budget, the judge without its branches),
    so it is scored 0 without spending a run."""
    problems: list[str] = []
    for component, text in candidate.items():
        if component not in COMPONENTS:
            problems.append(f"{component}: not an optimizable prompt (docs/05 §5 targets {', '.join(COMPONENTS)})")
            continue
        required = set(_PLACEHOLDER.findall(prompts.load(component, "base")))
        missing = sorted(required - set(_PLACEHOLDER.findall(text)))
        if missing:
            problems.append(
                f"{component}: the new text dropped the placeholders {', '.join(missing)}, which the system "
                "fills in at run time; without them the component never sees that input"
            )
    return problems


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def plan_view(record: RunRecord | None) -> str:
    """What the planner decided: its branches, and how many tasks each round ran."""
    if record is None or record.plan is None:
        return "(no plan was recorded for this run)"
    lines = [f"stop criteria: {record.plan.stop_criteria}"]
    lines += [
        f"- {branch.branch_id} [{branch.source_hint}, priority {branch.priority}]: {branch.question}"
        for branch in record.plan.branches
    ]
    rounds = Counter(task.round for task in record.tasks)
    per_round = ", ".join(f"round {number}: {count}" for number, count in sorted(rounds.items()))
    lines.append(f"tasks per round: {per_round or 'none'}")
    return "\n".join(lines)


def judge_view(record: RunRecord | None) -> str:
    """What the judge decided after each round."""
    if record is None or not record.verdicts:
        return "(the judge did not run on this run)"
    lines = []
    for verdict in record.verdicts:
        coverage = ", ".join(f"{branch} {state}" for branch, state in verdict.coverage.items()) or "none"
        lines.append(
            f"round {verdict.round}: {'sufficient' if verdict.sufficient else 'insufficient'}; "
            f"coverage: {coverage}; missing: {'; '.join(verdict.missing) or 'none'}; "
            f"new tasks: {len(verdict.new_tasks)}; reasoning: {_clip(verdict.reasoning or '', 300)}"
        )
    return "\n".join(lines)


def critic_view(record: RunRecord | None) -> str:
    """What the critic found after the judge was satisfied."""
    if record is None or not record.critic_reports:
        return "(the critic did not run on this run)"
    lines = []
    for report in record.critic_reports:
        interpretations = "; ".join(str(item) for item in report.missing_interpretations) or "none"
        lines.append(
            f"completion probability {report.completion_probability}; weak claims: {len(report.weak_claims)}; "
            f"missing interpretations: {_clip(interpretations, 300)}; "
            f"recommended searches: {len(report.recommended_searches)}; reasoning: {_clip(report.reasoning or '', 300)}"
        )
    return "\n".join(lines)


def usage_view(record: RunRecord | None) -> str:
    if record is None:
        return "no run record"
    usage = record.usage
    return (
        f"status {record.status}; {usage.searches} searches, {usage.fetches} fetches, {usage.agents} agents, "
        f"{usage.rounds} rounds, {usage.input_tokens + usage.output_tokens} tokens, {usage.wall_seconds}s"
    )


class PrimeAdapter:
    """GEPA's `GEPAAdapter` for PRIME. `runner` and `scorer` are injectable for tests."""

    # GEPA 0.1.4 reads this attribute directly; without it every proposal failed inside
    # GEPA's own try block, so no candidate was ever made and the budget went on re-running
    # the seed (spec review). None means GEPA's reflection model writes the new texts.
    propose_new_texts = None

    def __init__(
        self,
        records: Sequence[BenchRecord],
        *,
        budget: Budget,
        concurrency: int = 3,
        runner: Runner = run_prime,
        scorer: Scorer = score_record,
    ) -> None:
        self.records = {record.id: record for record in records}
        self.budget = budget
        self.concurrency = max(1, concurrency)
        self.runner = runner
        self.scorer = scorer
        # Every paid rollout, for reports/gepa-run.json.
        self.log: list[dict[str, Any]] = []
        # (prompt set, question id) -> its rollout. GEPA re-evaluates a parent on each new
        # minibatch and caches only dev evaluations, so without this a parent's train run
        # would be paid again every iteration.
        self._memo: dict[tuple[str, str], Rollout] = {}
        self.started_at: str | None = None
        self._lock = threading.Lock()

    def evaluate(
        self, batch: list[BenchRecord], candidate: dict[str, str], capture_traces: bool = False
    ) -> EvaluationBatch:
        holdout = [record.id for record in batch if record.split == "holdout"]
        if holdout:
            raise ValueError(f"refusing to evaluate holdout records {holdout}: optimization never sees holdout (docs/05 §5)")
        name = prompt_set_name(candidate)
        problems = candidate_problems(candidate)
        if problems:
            note = "The candidate was not run: " + "; ".join(problems)
            rollouts = [
                Rollout(record.id, None, "not_run", 0.0, None, note, "", "", "", "", error=note) for record in batch
            ]
            paid: list[Rollout] = []
        else:
            prompts.register_prompt_set(name, candidate)
            with self._lock:
                known = {record.id: self._memo.get((name, record.id)) for record in batch}
            todo = [record for record in batch if known[record.id] is None]
            with ThreadPoolExecutor(max_workers=max(1, min(self.concurrency, len(todo) or 1))) as pool:
                paid = list(pool.map(lambda record: self._rollout(record, name), todo))
            fresh = {rollout.question_id: rollout for rollout in paid}
            rollouts = [known[record.id] or fresh[record.id] for record in batch]
        with self._lock:
            for rollout in paid:
                self._memo[(name, rollout.question_id)] = rollout
            self.log.extend(
                {
                    "prompt_set": name,
                    "question_id": rollout.question_id,
                    "run_id": rollout.run_id,
                    "status": rollout.status,
                    "score": rollout.score,
                    "composite": rollout.composite,
                    "error": rollout.error,
                }
                for rollout in paid
            )
        return EvaluationBatch(
            outputs=rollouts,
            scores=[rollout.score for rollout in rollouts],
            trajectories=rollouts if capture_traces else None,
            # GEPA's metric budget counts paid runs only: a candidate that was not run and
            # a rollout reused from the memo cost nothing.
            num_metric_calls=len(paid),
        )

    def get_adapter_state(self) -> dict[str, Any]:
        """Saved in GEPA's checkpoint, so a `--run-dir` resume keeps the rollout log, the
        memo and the original start time."""
        with self._lock:
            return {
                "log": [dict(entry) for entry in self.log],
                "memo": [asdict(rollout) | {"prompt_set": key[0]} for key, rollout in self._memo.items()],
                "started_at": self.started_at,
            }

    def set_adapter_state(self, state: Mapping[str, Any]) -> None:
        with self._lock:
            self.log = [dict(entry) for entry in state.get("log", [])]
            self._memo = {}
            for item in state.get("memo", []):
                data = dict(item)
                prompt_set = data.pop("prompt_set")
                self._memo[(prompt_set, data["question_id"])] = Rollout(**data)
            if state.get("started_at"):
                self.started_at = state["started_at"]

    def _rollout(self, bench: BenchRecord, prompt_set: str) -> Rollout:
        request = RunRequest(
            question=bench.question, mode="prime", depth="deep", question_id=bench.id, budget_override=self.budget
        )
        ws = Workspace(objective=request.question, budget=self.budget)
        record: RunRecord | None = None
        error: str | None = None
        try:
            record = self.runner(
                request,
                ws=ws,
                source="gepa",
                extra_tags=[f"gepa:{bench.split}", f"candidate:{prompt_set}"],
                project_name=GEPA_PROJECT,
                prompt_set=prompt_set,
            )
        except Exception as exc:  # noqa: BLE001 - a failed run is scored as failed, not lost
            error = f"{type(exc).__name__}: {exc}"[:500]
            record = _saved_record(ws.run_id)
        scores = self.scorer(record, bench)
        value = composite(scores)
        if value is None and record is not None and record.answer is not None:
            # A judge failure leaves the composite empty; score once more before it counts as 0.
            scores = self.scorer(record, bench)
            value = composite(scores)
        feedback = feedback_text(scores)
        if value is None:
            feedback = "The run could not be scored (no answer or a judge failure); counted as 0.\n" + feedback
        return Rollout(
            question_id=bench.id,
            run_id=ws.run_id,
            status=record.status if record is not None else "failed",
            score=value if value is not None else 0.0,
            composite=value,
            feedback=_clip(feedback, MAX_FEEDBACK_CHARS),
            plan=plan_view(record),
            judge=judge_view(record),
            critic=critic_view(record),
            usage=usage_view(record),
            error=error,
        )

    def make_reflective_dataset(
        self, candidate: dict[str, str], eval_batch: EvaluationBatch, components_to_update: list[str]
    ) -> dict[str, list[dict[str, Any]]]:
        """Per component: the question it worked on, what it produced on that run, and the
        evaluators' feedback on the final answer (docs/05 §5)."""
        rollouts: Sequence[Rollout] = eval_batch.trajectories or eval_batch.outputs
        dataset: dict[str, list[dict[str, Any]]] = {}
        for component in components_to_update:
            items = []
            for rollout in rollouts:
                bench = self.records.get(rollout.question_id)
                feedback = f"composite score {rollout.score:.2f} ({rollout.usage})\n{rollout.feedback}"
                if rollout.error:
                    feedback += f"\nrun error: {rollout.error}"
                items.append(
                    {
                        "Inputs": {
                            "question": bench.question if bench else rollout.question_id,
                            "question_type": bench.question_type if bench else "",
                            "domain": bench.domain if bench else "",
                            "tier": str(bench.tier) if bench else "",
                        },
                        "Generated Outputs": getattr(rollout, component, "") or "(nothing recorded)",
                        "Feedback": feedback,
                    }
                )
            dataset[component] = items
        return dataset
