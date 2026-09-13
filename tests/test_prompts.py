"""Prompt loading. Every prompt is a Markdown file (CLAUDE.md), so the loader is
on the path of every LLM call and GEPA rewrites the files under prompts/optimized/.
"""

from __future__ import annotations

import pytest

from prime_search import prompts


@pytest.fixture(autouse=True)
def _clear_cache():
    prompts.load.cache_clear()
    yield
    prompts.load.cache_clear()


def test_loads_a_prompt_with_or_without_the_extension() -> None:
    assert prompts.load("smoke_plan") == prompts.load("smoke_plan.md")
    assert "fenced Python code block" in prompts.load("smoke_plan")


def test_missing_prompt_names_the_directory() -> None:
    with pytest.raises(FileNotFoundError, match="no-such-prompt"):
        prompts.load("no-such-prompt")


def test_render_substitutes_placeholders_without_touching_literal_braces() -> None:
    """smoke_plan.md contains a Python dict literal, so str.format would raise
    KeyError on the braces. This is why render uses replace."""
    out = prompts.render("smoke_plan", question="Is a CGM covered?")
    assert "Is a CGM covered?" in out
    assert "{question}" not in out
    assert '"branch_id": "b1"' in out  # the literal braces survived


def test_render_leaves_unknown_placeholders_alone() -> None:
    out = prompts.render("fenced_json", prompt="do the thing")
    assert "do the thing" in out
    assert "{schema}" in out  # not supplied, so not substituted


def test_optimized_prompt_set_falls_back_to_base_when_gepa_wrote_nothing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """docs/05 §5: GEPA writes prompts/optimized/. Until it does, or for a prompt it
    did not target, the base prompt must still load."""
    base = prompts.load("smoke_plan", prompt_set="base")
    assert prompts.load("smoke_plan", prompt_set="optimized") == base


def test_optimized_prompt_wins_when_present(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    optimized_dir = tmp_path / "optimized"
    optimized_dir.mkdir()
    (optimized_dir / "smoke_plan.md").write_text("OPTIMIZED", encoding="utf-8")
    (tmp_path / "smoke_plan.md").write_text("BASE", encoding="utf-8")
    monkeypatch.setattr(prompts, "_DIR", tmp_path)
    prompts.load.cache_clear()
    assert prompts.load("smoke_plan", prompt_set="optimized") == "OPTIMIZED"
    assert prompts.load("smoke_plan", prompt_set="base") == "BASE"


def test_every_1_7_prompt_renders_with_no_placeholder_left(sandboxed_run) -> None:
    """A prompt shipped with an unrendered {placeholder} sends the literal braces to the
    model. Each call site's keyword set is pinned against the file's own placeholders."""
    import re

    from prime_search.prompts import load, render

    call_sites = {
        "understand": {"question"},
        "plan": {
            "objective", "understanding", "workspace_api", "strategy_card",
            "min_branches", "max_branches", "budget",
        },
        "plan_repair": {"problem"},
        "synthesize": {"question", "understanding", "evidence", "claims", "review", "unresolved"},
        "judge": {
            "question", "stop_criteria", "branches", "unresolved", "budget", "round",
            "max_new_tasks",
        },
        "critic": {
            "question", "stop_criteria", "branches", "claims", "documents", "contested",
            "trajectory", "coverage", "review_mode",
        },
        "critic_repair": {"problem"},
        "baseline": set(),
    }
    for name, keys in call_sites.items():
        found = set(re.findall(r"\{([a-z_]+)\}", load(name)))
        assert found == keys, f"{name}: file has {sorted(found)}, call site passes {sorted(keys)}"
        rendered = render(name, "base", **dict.fromkeys(keys, "X"))
        assert not re.search(r"\{[a-z_]+\}", rendered), f"{name} still has a placeholder"


def test_the_synthesis_prompt_names_every_section_heading() -> None:
    """docs/03 §8's order is the contract the gate and the completeness evaluator read;
    if a heading is dropped from the prompt the model will not write it."""
    from prime_search.agents.synthesizer import SECTION_HEADINGS
    from prime_search.prompts import load

    text = load("synthesize")
    positions = [text.find(f"## {heading}") for heading in SECTION_HEADINGS]
    assert all(position > 0 for position in positions), dict(zip(SECTION_HEADINGS, positions))
    assert positions == sorted(positions)


def test_the_plan_prompt_states_the_fenced_python_output_rule() -> None:
    """docs/03 §11's seed checklist: "the fenced-Python output rule". Without it the
    planner falls to the structured-output rung on every run."""
    from prime_search.prompts import load

    text = load("plan").lower()
    assert "fenced python block" in text
    assert "ws.plan" in text


def test_the_judge_prompt_states_the_no_duplicate_and_resolved_rules() -> None:
    """docs/03 §11's seed checklist for judge.md."""
    from prime_search.prompts import load

    text = load("judge")
    assert "Never repeat an instruction or a query" in text
    assert "Never create a task for a branch you marked `resolved`" in text


def test_the_judge_prompt_separates_sufficiency_from_running_out() -> None:
    """Live run 2026-09-13 (adv-cgm-001): with 0 tokens left the judge set
    `sufficient: true` over partial coverage, reading "stop when the budget cannot buy a
    search" as permission to call the evidence enough."""
    from prime_search.prompts import load

    assert "Running out of budget or rounds is not sufficiency" in load("judge")


def test_the_critic_prompt_is_adversarial_and_emits_one_fenced_json_block() -> None:
    """docs/03 §11's seed checklist for critic.md: the §7 questions, the JSON schema,
    the instruction to be adversarial."""
    from prime_search.prompts import load

    text = load("critic")
    assert "adversarial" in text
    assert "Exactly one fenced `json` block" in text
    assert all(f"{n}. **" in text for n in range(1, 7))


def test_the_critic_prompt_asks_for_contradictions_a_reader_can_follow() -> None:
    """Live run 2026-09-13: the critic's only contradiction was "c5 claims ...; c6
    claims ..." about the LCD's own revision history - ids no reader sees, about dates
    that do not conflict."""
    from prime_search.prompts import load

    text = load("critic")
    assert "never sees claim ids" in text
    assert "revision history listing its earlier revision dates" in text


def test_the_plan_prompt_asks_for_a_secondary_source_branch_on_contradiction_questions() -> None:
    """The contradiction SearchBench's adversarial records expect is "secondary sources
    overstate coverage vs the LCD". Three live runs of adv-cgm-001 planned only
    primary-policy branches, so that conflict was never gathered."""
    from prime_search.prompts import load

    text = " ".join(load("plan").split())
    assert "`eligibility`, `coverage_pathway` or `contradiction`" in text
    assert "no more than two branches" in text
    assert 'source_hint="any"' in text


def test_the_search_agent_records_what_a_secondary_page_claims_when_asked_to() -> None:
    """Rule 1 made every secondary page a pointer only, which left a secondary-source
    branch with nothing it was allowed to record."""
    from prime_search.prompts import load

    text = " ".join(load("search_agent").split())
    assert "the secondary page's own passage *is* the evidence" in text
