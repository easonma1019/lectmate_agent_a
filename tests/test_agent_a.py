"""Unit tests for Agent A (stub mode — no API key required).

These are the 'test at agent-A level before handing to B' checks the
company asked for in the 2 Jul meeting.
"""
import pytest
from pydantic import ValidationError

from agent_a import AgeBracket, CourseRequest, Subject, plan_course, rule_check
from agent_a.concept_graph import toposort_check
from agent_a.html_report import render_course_spec_html, write_course_spec_html
from agent_a.pedagogy import lookup
from agent_a.schemas import CoursePhase, CourseSpec, ModuleSpec


def _req(age=AgeBracket.CREATORS, **kw):
    return CourseRequest(
        subject=Subject.CODING, age_bracket=age, topic="Python fundamentals", **kw
    )


# --- happy path -------------------------------------------------------------

@pytest.mark.parametrize("age", list(AgeBracket))
def test_stub_plan_valid_for_all_tiers(age):
    spec = plan_course(_req(age=age), use_llm=False)
    assert spec.subject == Subject.CODING
    assert spec.pedagogy.tier in (1, 2, 3, 4)
    assert len(spec.modules) >= 1
    assert rule_check(spec) == []


def test_session_cap_respected():
    spec = plan_course(_req(age=AgeBracket.EXPLORERS), use_llm=False)
    for m in spec.modules:
        assert m.target_minutes <= 20  # T03 hard limit for tier 1


def test_module_count_follows_pacing_template():
    younger = plan_course(_req(age=AgeBracket.EXPLORERS), use_llm=False)
    older = plan_course(_req(age=AgeBracket.LEADERS), use_llm=False)
    assert len(younger.modules) > len(older.modules)  # more, shorter modules when younger


def test_max_modules_override():
    spec = plan_course(_req(max_modules=3), use_llm=False)
    assert len(spec.modules) == 3


def test_html_report_renders_course_review_page(tmp_path):
    spec = plan_course(_req(max_modules=2), use_llm=False)

    html = render_course_spec_html(spec)
    assert "LectMate Agent A Course Pages" in html
    assert "Level A - Landing Page Card" in html
    assert "Level B - Course Overview Page (Pre-Login)" in html
    assert "Level C - Full Course Page (Post-Login)" in html
    assert "Python fundamentals" in html
    assert spec.modules[0].title in html
    assert spec.phases[0].title in html
    assert "Raw CourseSpec JSON" in html

    output_path = write_course_spec_html(spec, tmp_path / "review.html")
    assert output_path.exists()
    assert output_path.as_uri().startswith("file://")


# --- schema guards ----------------------------------------------------------

def _minimal_spec(modules):
    return dict(
        course_id="t",
        subject=Subject.CODING,
        age_bracket=AgeBracket.CREATORS,
        topic="t",
        pedagogy=lookup(AgeBracket.CREATORS),
        modules=modules,
    )


def test_forward_prerequisite_rejected():
    mods = [
        ModuleSpec(module_id="m1", title="a", objective="Understand x",
                   prerequisites=["m2"], target_minutes=30,
                   exercise_type="fill_in_the_blank"),
        ModuleSpec(module_id="m2", title="b", objective="Understand y",
                   prerequisites=[], target_minutes=30,
                   exercise_type="fill_in_the_blank"),
    ]
    with pytest.raises(ValidationError, match="appears later"):
        CourseSpec(**_minimal_spec(mods))


def test_over_cap_minutes_rejected():
    mods = [
        ModuleSpec(module_id="m1", title="a", objective="Understand x",
                   prerequisites=[], target_minutes=90,  # cap for Creators is 35
                   exercise_type="fill_in_the_blank"),
    ]
    with pytest.raises(ValidationError, match="hard cap"):
        CourseSpec(**_minimal_spec(mods))


def test_phase_must_cover_each_module_once():
    mods = [
        ModuleSpec(module_id="m1", title="a", objective="Understand x",
                   prerequisites=[], target_minutes=30,
                   exercise_type="fill_in_the_blank"),
        ModuleSpec(module_id="m2", title="b", objective="Understand y",
                   prerequisites=["m1"], target_minutes=30,
                   exercise_type="fill_in_the_blank"),
    ]
    with pytest.raises(ValidationError, match="cover every module"):
        CourseSpec(
            **_minimal_spec(mods),
            phases=[
                CoursePhase(
                    phase_id="p1",
                    title="Only the first module",
                    module_ids=["m1"],
                )
            ],
        )


def test_compound_objective_rejected():
    with pytest.raises(ValidationError, match="compound"):
        ModuleSpec(module_id="m1", title="a",
                   objective="Understand loops; also master functions",
                   prerequisites=[], target_minutes=30,
                   exercise_type="fill_in_the_blank")


def test_wrong_tier_exercise_flagged_by_rule_check():
    spec = plan_course(_req(age=AgeBracket.EXPLORERS), use_llm=False)
    spec.modules[0].exercise_type = "code_review"  # tier-4 exercise for a 7-year-old
    problems = rule_check(spec)
    assert any("not allowed for tier" in p for p in problems)


# --- concept graph ----------------------------------------------------------

def test_toposort_detects_out_of_order():
    problems = toposort_check(["loops", "conditionals"])  # loops depends on conditionals
    assert problems and "before its prerequisite" in problems[0]


def test_toposort_accepts_valid_order():
    assert toposort_check(["variables", "conditionals", "loops"]) == []
