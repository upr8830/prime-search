"""The root's workspace and its sandboxed REPL (docs/02 §3, docs/03 §12).

The workspace is the RLM property made concrete: search results, documents and
evidence accumulate in *variables*, and the root reasons over them by executing
small code cells instead of re-reading everything through its context. A 79 KB LCD
never enters a prompt; the root looks at `ws.documents[id].title`, paragraph counts,
and calls `ws.search_within(...)` for the handful of paragraphs it actually needs.

Two decisions worth stating up front, both forced by the specs disagreeing:

* **`search_within` is a Workspace method, not a global.** docs/03 §12 says the cell
  namespace holds `ws`, the schema classes, `date`, `datetime` "and nothing else";
  docs/01 §8 says it exposes "the primitives and workspace helpers"; docs/02 §3 has
  the root calling `search_within` to see specific paragraphs. Hanging it off `ws`
  satisfies all three, and keeps deep-read budget accounting on the object that owns
  the budget. `search` and `fetch` are deliberately *not* reachable from a cell:
  docs/03 §4 gives those to the sub-agents.
* **The timeout is a thread, not `signal.alarm`.** docs/03 §12 allows either;
  `signal.alarm` is Unix-only and this build runs on Windows. A join timeout alone
  only *abandons* a runaway cell, and a thread busy-looping in pure Python holds the
  GIL tightly enough to hang interpreter shutdown — `while True: pass` really did
  stop the CLI from exiting. So the cell also carries a line-level trace hook that
  raises once the deadline passes, and the join is the backstop.

The sandbox is a guard against a language model's mistakes, not a security boundary
against an attacker: `getattr` and attribute traversal can still reach objects the
allowlist does not name, and a timed-out cell that could not be interrupted is free
to keep mutating `ws`. Nothing in the specs asks for more, and the cell's author is
our own root prompt. What *is* enforced is that `search_within` reads only inside
this run's document directories, so docs/01 §8's "no file I/O" is not crossed by a
cell naming a path of its own.
"""

from __future__ import annotations

import io
import secrets
import sys
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from prime_search.config import Budget, get_settings
from prime_search.primitives import sources, within
from prime_search.schemas import (
    Answer,
    Branch,
    Citation,
    Claim,
    CriticReport,
    Document,
    Evidence,
    Location,
    QueryUnderstanding,
    SearchPlan,
    SearchTask,
    TaskResult,
    Usage,
    Verdict,
)

# docs/03 §12 caps cell output at 4k. Long enough for a plan or a paragraph list,
# short enough that `print(ws.evidence)` cannot flood the root's next prompt.
MAX_STDOUT_CHARS = 4000
TRUNCATION_NOTE = "\n... [output truncated at {limit} chars]"
# Not specified anywhere. A planning cell is arithmetic over objects already in
# memory, so seconds are generous; small enough that a runaway loop costs nothing.
DEFAULT_TIMEOUT_SECONDS = 5.0

# docs/03 §12: "Builtins reduced to a safe subset (no open, __import__, eval, exec)."
# The allowlist is this build's (the spec names only the four denials). Everything
# here is pure computation over objects the cell already has.
_SAFE_BUILTIN_NAMES = (
    # values and computation
    "abs", "all", "any", "bool", "dict", "dir", "divmod", "enumerate", "filter",
    "float", "format", "frozenset", "getattr", "hasattr", "int", "isinstance",
    "issubclass", "iter", "len", "list", "map", "max", "min", "next", "range",
    "repr", "reversed", "round", "set", "setattr", "slice", "sorted", "str", "sum",
    "tuple", "type", "zip", "True", "False", "None",
    # `class` statements compile to a __build_class__ lookup, so without this a cell
    # defining a helper class fails with an unexplainable NameError.
    "__build_class__", "__name__",
    # A cell that writes a defensive try/except must be able to name what it catches.
    "ArithmeticError", "AttributeError", "Exception", "IndexError", "KeyError",
    "LookupError", "NameError", "NotImplementedError", "RuntimeError",
    "StopIteration", "TypeError", "ValueError", "ZeroDivisionError",
)
_SAFE_BUILTINS: dict[str, Any] = {
    name: (
        __builtins__[name] if isinstance(__builtins__, dict) else getattr(__builtins__, name)
    )
    for name in _SAFE_BUILTIN_NAMES
    if (name in __builtins__ if isinstance(__builtins__, dict) else hasattr(__builtins__, name))
}


def new_run_id() -> str:
    """A uuid7-shaped, time-ordered id (docs/02 §2.1).

    The stdlib gains `uuid.uuid7()` in 3.14 and this build targets 3.11-3.13, so the
    layout is assembled here rather than taking a dependency for sixteen bytes. Time
    ordering is the point: `runs/` sorts chronologically in a file listing.
    """
    # RFC 9562 §5.7: 48 bits of unix_ts_ms, version 7, 12 random, variant 10, 62
    # random. `uuid.UUID(version=7)` is rejected before 3.14, so the bits are set
    # here and the int handed over as-is.
    timestamp_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    value = (
        (timestamp_ms << 80)
        | (0x7 << 76)
        | (secrets.randbits(12) << 64)
        | (0b10 << 62)
        | secrets.randbits(62)
    )
    return str(uuid.UUID(int=value))


class DeepReadBudgetExceeded(ValueError):
    """`max_deep_reads` is spent (docs/01 §3).

    A distinct type because the sub-agent has to tell this apart from every other
    `ValueError` this method raises — an unreadable path, a snippet-only document,
    offsets that drifted — and it was doing so by looking for the word "budget" in the
    message, which held only until someone reworded an error string. Subclasses
    `ValueError` so existing callers that catch that still behave.
    """


@dataclass(slots=True)
class ExecResult:
    """Outcome of one sandboxed cell.

    docs/03 §12 never defines this type. It returns errors *as text* rather than
    raising, because the caller is a language model that gets one repair turn — a
    traceback is the most useful thing to hand back.
    """

    ok: bool
    stdout: str = ""
    error: str | None = None
    timed_out: bool = False
    seconds: float = 0.0

    def as_text(self) -> str:
        """What the root sees after its cell runs."""
        if self.timed_out:
            return f"TIMEOUT after {self.seconds:.1f}s — the cell was abandoned.\n{self.stdout}"
        if not self.ok:
            return f"{self.stdout}\nERROR:\n{self.error}".strip()
        return self.stdout or "(no output)"


@dataclass
class Workspace:
    """Everything one run knows (docs/02 §3).

    A plain object rather than a Pydantic model: nodes mutate it in place and return
    it (docs/03 §1), and `RunRecord` is the serialized form. `to_record()` is the
    bridge.
    """

    objective: str
    budget: Budget = field(default_factory=Budget)
    understanding: QueryUnderstanding | None = None
    plan: SearchPlan | None = None
    tasks: list[SearchTask] = field(default_factory=list)
    documents: dict[str, Document] = field(default_factory=dict)
    evidence: list[Evidence] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    run_id: str = field(default_factory=new_run_id)
    # Captured when the workspace is created, which is when the run begins. Timezone
    # aware, matching Document.retrieved_at.
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # --- views ------------------------------------------------------------------

    @property
    def search_tree(self) -> dict[str, dict[str, Any]]:
        """branch_id -> {tasks, evidence_ids, status} (docs/02 §3).

        Derived rather than maintained, so it can never disagree with `tasks` and
        `evidence`. The UI's search tree renders this.
        """
        tree: dict[str, dict[str, Any]] = {}
        for task in self.tasks:
            node = tree.setdefault(
                task.branch_id, {"tasks": [], "evidence_ids": [], "status": "pending"}
            )
            node["tasks"].append(task.task_id)
        for item in self.evidence:
            node = tree.setdefault(
                item.branch_id, {"tasks": [], "evidence_ids": [], "status": "pending"}
            )
            node["evidence_ids"].append(item.evidence_id)
        for branch_id, node in tree.items():
            statuses = {task.status for task in self.tasks if task.branch_id == branch_id}
            if statuses and statuses <= {"done", "failed"}:
                node["status"] = "resolved" if node["evidence_ids"] else "unresolved"
            elif "running" in statuses:
                node["status"] = "running"
            elif not statuses and node["evidence_ids"]:
                # Evidence carried over from an earlier round with no task of its own
                # this round: reporting "pending" forever would make the branch look
                # stuck to both the judge and the UI.
                node["status"] = "resolved"
        return tree

    def budget_remaining(self) -> Budget:
        """What is left of the run's allowance (docs/02 §3).

        Floored at zero: a node asking "how many searches may I still do" must never
        be handed a negative number to compare against.
        """
        used = self.usage
        limit = self.budget
        return Budget(
            max_searches=max(0, limit.max_searches - used.searches),
            max_fetches=max(0, limit.max_fetches - used.fetches),
            max_deep_reads=max(0, limit.max_deep_reads - used.deep_reads),
            max_agents=max(0, limit.max_agents - used.agents),
            max_rounds=max(0, limit.max_rounds - used.rounds),
            max_tokens=max(0, limit.max_tokens - used.input_tokens - used.output_tokens),
            max_seconds=max(0, int(limit.max_seconds - used.wall_seconds)),
        )

    # --- helpers the root calls from a cell -------------------------------------

    def evidence_for(self, branch_id: str) -> list[Evidence]:
        """docs/02 §3."""
        return [item for item in self.evidence if item.branch_id == branch_id]

    def docs_by_tier(self, tier: sources.Tier, *, at_least: bool = False) -> list[Document]:
        """Documents at a tier, or at that tier and better when `at_least` is set.

        docs/02 §3 names only the exact form, but docs/04 §1's consumer rule and
        docs/05's `primary_source_ratio` both ask "is this official or better", so
        both readings are available rather than forcing callers to re-derive one.
        """
        if at_least:
            return [
                document
                for document in self.documents.values()
                if sources.at_least(document.source_tier, tier)
            ]
        return [
            document for document in self.documents.values() if document.source_tier == tier
        ]

    def dates(self) -> list[tuple[str, date | None]]:
        """(doc_id, governing date) for every fetched document (docs/02 §3).

        The governing date is `revision_date or effective_date`, not `effective_date`
        alone: measured on the live pages, both CMS flagship documents state a
        revision date and no effective date, so an effective-date-only helper would
        return nothing for exactly the documents docs/03 §12 cites as its reason for
        existing.
        """
        return [
            (document.doc_id, document.revision_date or document.effective_date)
            for document in self.documents.values()
            if document.is_fetched
        ]

    def search_within(self, doc_id: str, query: str, k: int = 5) -> list[dict[str, object]]:
        """BM25 over one fetched document's paragraphs (docs/02 §3, docs/03 §4).

        Counts against `max_deep_reads`. Returns plain dicts so a cell can print them
        without a repr that floods the 4k output cap.
        """
        document = self.documents.get(doc_id)
        if document is None:
            raise KeyError(f"no document {doc_id!r} in the workspace; search first")
        remaining = self.budget_remaining().max_deep_reads
        if remaining <= 0:
            raise DeepReadBudgetExceeded(
                f"deep-read budget exhausted ({self.budget.max_deep_reads} used); "
                "answer from the evidence already gathered"
            )
        # Charged here, before any work: docs/01 §9 counts a call that fails, and
        # every failure below this line (an unreadable path, a missing text file,
        # offsets that drifted) is a call that was really made. Only the two raises
        # above happen without spending anything.
        self.usage.deep_reads += 1
        _assert_readable(document.text_path)
        return [passage.as_dict() for passage in within.search_within(document, query, k=k)]

    # --- persistence -------------------------------------------------------------

    def to_record(self, request: Any, **overrides: Any) -> Any:
        """Project the workspace into the persisted `RunRecord` (docs/02 §2.1, §5).

        The workspace holds what the *search* produced; `verdicts`, `critic_reports`,
        `answer`, `finished_at`, `langsmith_run_url` and the terminal `status` belong
        to the graph around it and are passed as overrides. `started_at` comes from
        the workspace rather than the clock: stamping it here would record the moment
        the record was written, which is the run's end.

        Imported lazily so `schemas` never depends on this module.
        """
        from prime_search.schemas import RunRecord

        payload: dict[str, Any] = {
            "run_id": self.run_id,
            "request": request,
            "started_at": self.started_at,
            "plan": self.plan,
            "tasks": self.tasks,
            "documents": self.documents,
            "evidence": self.evidence,
            "claims": self.claims,
            "usage": self.usage,
        }
        payload.update(overrides)
        return RunRecord(**payload)

    # --- the sandbox --------------------------------------------------------------

    def exec(self, code: str, *, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> ExecResult:
        """Run one code cell against this workspace (docs/03 §12).

        The cell sees `ws` (this object, not a copy — mutations are the point), the
        schema classes, `date` and `datetime`. Builtins are the reduced set above.
        stdout is captured and returned; an exception comes back as text so the root
        can repair it on its next turn.

        Each cell gets a fresh namespace. A failed cell therefore leaves no
        half-bound locals behind for the repair turn to trip over, and the only state
        that carries between cells is `ws` itself — which is the design.
        """
        namespace: dict[str, Any] = {
            "__builtins__": _SAFE_BUILTINS,
            "ws": self,
            "date": date,
            "datetime": datetime,
            # The schema classes, so a cell can construct a plan by name.
            "Answer": Answer,
            "Branch": Branch,
            "Citation": Citation,
            "Claim": Claim,
            "CriticReport": CriticReport,
            "Document": Document,
            "Evidence": Evidence,
            "Location": Location,
            "QueryUnderstanding": QueryUnderstanding,
            "SearchPlan": SearchPlan,
            "SearchTask": SearchTask,
            "TaskResult": TaskResult,
            "Usage": Usage,
            "Verdict": Verdict,
            "Budget": Budget,
        }

        buffer = io.StringIO()
        outcome: dict[str, Any] = {"ok": False, "error": None, "timed_out": False}
        deadline = time.monotonic() + timeout

        def cell_print(*values: Any, sep: str = " ", end: str = "\n") -> None:
            """The cell's `print`, bound to this cell's buffer.

            Not `contextlib.redirect_stdout`: that swaps `sys.stdout` process-wide, so
            for the duration of a cell every other thread's output — structlog on
            stderr, a streaming answer on stdout — would be captured into this buffer
            too. Owning `print` keeps the capture thread-local by construction.
            """
            buffer.write(sep.join(str(value) for value in values) + end)

        namespace["print"] = cell_print

        def run() -> None:
            # A join timeout alone only *abandons* a runaway cell, and a thread
            # busy-looping in pure Python holds the GIL hard enough to hang
            # interpreter shutdown. A line-level trace hook raises inside the cell
            # instead, so `while True: pass` actually stops. It cannot interrupt a
            # blocking C call, but the namespace has no I/O to block on.
            def trace(frame: Any, event: str, arg: Any) -> Any:
                if time.monotonic() > deadline:
                    raise TimeoutError(f"cell exceeded {timeout:g}s")
                return trace

            try:
                sys.settrace(trace)
                exec(compile(code, "<cell>", "exec"), namespace)  # noqa: S102
                outcome["ok"] = True
            except TimeoutError as exc:
                outcome["timed_out"] = True
                outcome["error"] = str(exc)
            except BaseException:  # SyntaxError included; the root repairs it
                outcome["error"] = _format_exception()
            finally:
                sys.settrace(None)

        started = time.monotonic()
        # daemon=True so that a cell the trace hook cannot reach still never keeps
        # the process alive.
        thread = threading.Thread(target=run, name="sandbox-exec", daemon=True)
        thread.start()
        # A little slack past the deadline: the trace hook should fire first, and the
        # join is the backstop for a cell it could not interrupt.
        thread.join(timeout + 0.5)
        seconds = time.monotonic() - started

        if thread.is_alive():
            return ExecResult(
                ok=False,
                stdout=_truncate(buffer.getvalue()),
                error=f"cell exceeded {timeout:g}s and could not be interrupted",
                timed_out=True,
                seconds=seconds,
            )
        return ExecResult(
            ok=bool(outcome["ok"]),
            stdout=_truncate(buffer.getvalue()),
            error=outcome["error"],
            timed_out=bool(outcome["timed_out"]),
            seconds=seconds,
        )


def _assert_readable(text_path: str) -> None:
    """Keep `search_within` inside the directories this run actually wrote.

    docs/01 §8 says the sandbox performs no file I/O. Reading a paragraph out of an
    already-fetched document is the design (docs/02 §3), but a cell can put a
    `Document` of its own into `ws.documents` — the class is in the namespace — and
    a naive lookup would then read any path it named. Mediated access to the run's
    own text is the intent; arbitrary reads are not.
    """
    if not text_path:
        return  # snippet_only; within.load_text raises its own clearer error
    # Imported here rather than at module scope: events imports nothing from this
    # module, but the run directory is its definition to own, not ours to hardcode.
    # Hardcoding Path("runs") made search_within refuse a document the agent had just
    # fetched whenever the runs root moved — which is every test, and would be any
    # deployment that relocates it.
    from prime_search.events import runs_root

    resolved = Path(text_path).resolve()
    allowed = [Path(get_settings().tavily_cache_dir).resolve(), runs_root().resolve()]
    if not any(resolved.is_relative_to(root) for root in allowed):
        raise ValueError(
            f"{resolved} is outside this run's document directories; "
            "search_within only reads documents this run fetched"
        )


def _truncate(text: str, limit: int = MAX_STDOUT_CHARS) -> str:
    """docs/03 §12: <= 4k chars, truncated with a note."""
    if len(text) <= limit:
        return text
    return text[:limit] + TRUNCATION_NOTE.format(limit=limit)


def _format_exception() -> str:
    """The traceback with the harness frames removed: the root only needs its cell.

    Frames are dropped in pairs — a `File "..."` line plus the source line under it —
    rather than by substring. Filtering on "in run" or "workspace.py" anywhere in the
    line also ate the final `ValueError: ... in run order` message, leaving the root a
    traceback with no exception on the end and nothing to repair; and it left behind
    the harness's own `exec(compile(...))` source line, so every cell error opened by
    showing the root a call to the `exec` it is told it cannot use.
    """
    lines = traceback.format_exc().splitlines()
    kept: list[str] = []
    skip_source_line = False
    for line in lines:
        if line.lstrip().startswith('File "') and "workspace.py" in line:
            skip_source_line = True  # and drop the source line that follows it
            continue
        if skip_source_line:
            skip_source_line = False
            if line.startswith("    "):  # the frame's source, not the next frame
                continue
        kept.append(line)
    return "\n".join(kept).strip()


def new_workspace(objective: str, depth: str = "deep") -> Workspace:
    """A workspace with the budget for `depth` (docs/01 §3)."""
    return Workspace(objective=objective, budget=get_settings().budget(depth))
