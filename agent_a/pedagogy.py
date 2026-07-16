"""
T03 Content Design Matrix, encoded as data.

Source: 'LectMate · Age-Stratified Pedagogy Research & Content Design Matrix'
(Sprint 1, Yisong). Each entry is a design RULE, not a suggestion — the
Planner looks up the tier and injects the constraints into the CourseSpec.

Age-tier lookup happens BEFORE any other planner logic (doc §5.1): it gates
all downstream constraints.
"""
from __future__ import annotations

from .schemas import AgeBracket, PedagogyConstraints

# Tier column of the matrix, one entry per age bracket -----------------------

_MATRIX: dict[AgeBracket, PedagogyConstraints] = {
    AgeBracket.EXPLORERS: PedagogyConstraints(
        tier=1,
        cognitive_theory="Piaget concrete operational",
        csta_level="Level 1A (K-2)",
        raw_text_code_allowed="never",
        content_format="story+visual",
        metaphor_story="mandatory",
        exercise_types=[
            "sequence_ordering",
            "drag_drop_blocks",
            "spot_the_error_visual",
            "story_completion",
        ],
        mini_project_type="animation / interactive story / simple game",
        max_session_min=20,
        tester_mode="logic_check",
        tutor_guide_style="physical_analogy_script",
        feedback_style="immediate_visual",
        key_csta_standards=["1A-AP-08", "1A-AP-10", "1A-AP-11", "1A-AP-15"],
    ),
    AgeBracket.CREATORS: PedagogyConstraints(
        tier=2,
        cognitive_theory="Vygotsky ZPD + scaffolding",
        csta_level="Level 1B + Level 2 (Gr 3-8)",
        raw_text_code_allowed="limited",
        content_format="scaffold_text",
        metaphor_story="recommended",
        exercise_types=[
            "fill_in_the_blank",
            "fix_the_bug_simple",
            "short_write_max5lines",
            "flowchart_design",
        ],
        mini_project_type="calculator / quiz game / simple utility",
        max_session_min=35,
        tester_mode="simple_exec",
        tutor_guide_style="scaffolded_hint_sequence",
        feedback_style="immediate_plus_explain_why",
        key_csta_standards=["1B-AP-08", "1B-AP-10", "1B-AP-15", "2-AP-10", "2-AP-13", "2-AP-17"],
    ),
    AgeBracket.INNOVATORS: PedagogyConstraints(
        tier=3,
        cognitive_theory="Piaget formal operations + project-based learning",
        csta_level="Level 2 + Level 3A (Gr 6-10)",
        raw_text_code_allowed="yes",
        content_format="text_project",
        metaphor_story="optional",
        exercise_types=[
            "function_build",
            "debug_real_error",
            "feature_add_extend",
            "algorithm_comparison",
        ],
        mini_project_type="practical tool / data analysis script / simple web page",
        max_session_min=60,
        tester_mode="sandbox_exec",
        tutor_guide_style="socratic_question_chain",
        feedback_style="delayed_reflective",
        key_csta_standards=["3A-AP-13", "3A-AP-15", "3A-AP-17", "3A-AP-23"],
    ),
    AgeBracket.LEADERS: PedagogyConstraints(
        tier=4,
        cognitive_theory="Andragogy (Knowles)",
        csta_level="Level 3B (Gr 11-12+)",
        raw_text_code_allowed="yes",
        content_format="engineering",
        metaphor_story="not_needed",
        exercise_types=[
            "system_design",
            "api_integration",
            "code_review",
            "refactoring_efficiency",
        ],
        mini_project_type="full web app / REST API / ML model integration",
        max_session_min=90,
        tester_mode="sandbox_plus_testsuite",
        tutor_guide_style="peer_review_checklist",
        feedback_style="peer_review_self_assessment",
        key_csta_standards=["3B-AP-08", "3B-AP-10", "3B-AP-14", "3B-AP-21", "3B-AP-24"],
    ),
}

# Module count & pacing templates per tier (Game Plan §5: shorter, more
# numerous modules with repetition for younger tiers; fewer, deeper for older).
PACING: dict[AgeBracket, dict] = {
    AgeBracket.EXPLORERS: {"default_modules": 8, "default_minutes": 15},
    AgeBracket.CREATORS: {"default_modules": 6, "default_minutes": 30},
    AgeBracket.INNOVATORS: {"default_modules": 5, "default_minutes": 50},
    AgeBracket.LEADERS: {"default_modules": 4, "default_minutes": 75},
}


def lookup(age_bracket: AgeBracket) -> PedagogyConstraints:
    """Age-tier lookup — the gate for all downstream constraints."""
    return _MATRIX[age_bracket].model_copy(deep=True)


def pacing(age_bracket: AgeBracket) -> dict:
    return dict(PACING[age_bracket])
