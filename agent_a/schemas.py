"""
Shared data contract — Agent A side.

Implements the frozen schema from the Game Plan §4.1 (CourseRequest -> CourseSpec),
extended with two fields raised in the 2 Jul meeting:
  - `references`      : grounding sources Agent A consulted / recommends (checked later by Agent C)
  - `relevancy_note`  : Agent A's topic-currency check result
and the pedagogy constraints block from the T03 Content Design Matrix, which is
what Agent B injects into its generation prompt.

Any change to field names here is a TEAM decision (see Game Plan §9) — log it in
the shared changelog before merging.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Subject(str, Enum):
    CODING = "Coding"
    AI = "AI"
    FINANCIAL_LITERACY = "Financial Literacy"
    ENTREPRENEURSHIP = "Entrepreneurship"


class AgeBracket(str, Enum):
    EXPLORERS = "Explorers (6-9)"
    CREATORS = "Creators (10-13)"
    INNOVATORS = "Innovators (14-17)"
    LEADERS = "Leaders (18-21)"


class PlanningMode(str, Enum):
    FIXED_PEDAGOGY = "fixed"
    ADDIE_DISCOVERY = "addie"


# ---------------------------------------------------------------------------
# Input: course request
# ---------------------------------------------------------------------------

class CourseRequest(BaseModel):
    """What the curriculum engineer submits. Kept deliberately simple
    (subject + age + objectives) per the 2 Jul meeting decision; the
    `source` field is the extension hook for the future trend-detection
    input the company mentioned."""

    subject: Subject
    age_bracket: AgeBracket
    topic: str = Field(..., min_length=3, description="e.g. 'Python fundamentals'")
    learning_objectives: list[str] = Field(
        default_factory=list,
        description="Optional high-level goals from the requester; Agent A refines them.",
    )
    design_requirements: list[str] = Field(
        default_factory=list,
        description="Course designer requirements, constraints, or preferences.",
    )
    max_modules: Optional[int] = Field(default=None, ge=1, le=20)
    planning_mode: PlanningMode = Field(
        default=PlanningMode.FIXED_PEDAGOGY,
        description="'fixed' uses the local pedagogy matrix; 'addie' performs Analyze/Design discovery.",
    )
    source: str = Field(
        default="manual",
        description="Where the request came from: 'manual' | 'trend_agent' | ...",
    )

    @field_validator("topic")
    @classmethod
    def topic_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("topic must not be blank")
        return v


# ---------------------------------------------------------------------------
# Pedagogy constraints (from the T03 Content Design Matrix)
# ---------------------------------------------------------------------------

class PedagogyConstraints(BaseModel):
    """The tier column of the T03 matrix, injected verbatim into every module
    so Agent B never has to guess. Field names mirror the 'Planner constraint
    examples' row of the matrix."""

    tier: int = Field(..., ge=1, le=4)
    cognitive_theory: str
    csta_level: str
    raw_text_code_allowed: str  # "never" | "limited" | "yes"
    content_format: str
    metaphor_story: str  # "mandatory" | "recommended" | "optional" | "not_needed"
    exercise_types: list[str]
    mini_project_type: str
    max_session_min: int
    tester_mode: str
    tutor_guide_style: str
    feedback_style: str
    key_csta_standards: list[str]


# ---------------------------------------------------------------------------
# Output: course spec
# ---------------------------------------------------------------------------

class Reference(BaseModel):
    """Grounding source: where the curriculum framework / content should come
    from. Stored so Agent C can verify against it (2 Jul meeting)."""

    title: str
    kind: str = Field(..., description="'standard' | 'textbook' | 'web' | 'paper'")
    identifier: str = Field(..., description="CSTA code, ISBN, URL, or DOI")


class ModuleSpec(BaseModel):
    module_id: str = Field(..., pattern=r"^m\d+$")
    title: str
    objective: str = Field(..., description="Exactly ONE clear learning objective.")
    prerequisites: list[str] = Field(default_factory=list)
    target_minutes: int = Field(..., ge=5, le=120)
    exercise_type: str
    csta_alignment: list[str] = Field(
        default_factory=list, description="CSTA standard codes this module addresses."
    )

    @field_validator("objective")
    @classmethod
    def single_objective(cls, v: str) -> str:
        """Reject obviously compound objectives ('... and ...' joining two verbs).
        Heuristic, not perfect — the rule validator does a second pass."""
        v = v.strip()
        if not v:
            raise ValueError("objective must not be blank")
        if v.count(";") >= 1:
            raise ValueError("objective looks compound (contains ';') — write one objective")
        return v


class CourseOverview(BaseModel):
    """Human-facing course copy used by Level A/B/C display surfaces.

    These fields do not replace the machine handoff contract. They give
    product pages enough structured copy to render landing, pre-login, and
    full course views without asking the frontend to invent curriculum text.
    """

    level: str = Field(default="", description="e.g. Beginner | Intermediate")
    lesson_range: str = Field(default="", description="e.g. 20-24 lessons")
    duration: str = Field(default="", description="e.g. 10-12 weeks")
    tagline: str = Field(default="")
    one_sentence_description: str = Field(default="")
    skill_tags: list[str] = Field(default_factory=list)
    what_you_will_learn: list[str] = Field(default_factory=list)
    what_you_will_build: str = Field(default="")
    why_this_course: str = Field(default="")
    learning_outcomes: list[str] = Field(default_factory=list)
    tools_you_will_use: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    progress_tracking: list[str] = Field(default_factory=list)


class CoursePhase(BaseModel):
    """A product-facing grouping of modules for the full course page."""

    phase_id: str = Field(..., pattern=r"^p\d+$")
    title: str
    module_ids: list[str] = Field(..., min_length=1)


class ComponentBankSpec(BaseModel):
    """One master resource bank and how it is split by module."""

    folder_name: str
    master_file: str
    per_module_unit: str
    units_per_module: Optional[int] = None
    total_units: Optional[int] = None
    split_file_name: str
    split_by_module: bool = True


class ModulePackageSpec(BaseModel):
    """The exact per-module join key and split-file names across banks."""

    module_id: str
    module_index: int
    module_title: str
    folder_title: str
    folder_name: str
    slides_file: str
    exercises_file: str
    questions_file: str
    assignments_file: str


class CoursePackagingPlan(BaseModel):
    """Automation contract for course banks, folders, and split outputs."""

    bank_folders: list[str] = Field(default_factory=list)
    component_banks: list[ComponentBankSpec] = Field(default_factory=list)
    module_packages: list[ModulePackageSpec] = Field(default_factory=list)
    relationships: list[str] = Field(default_factory=list)
    validation_checklist: list[str] = Field(default_factory=list)
    exercises_per_module: int = 6
    quiz_questions_per_module: int = 10
    assignments_per_module: int = 3


class ADDIEAnalysis(BaseModel):
    """Analyze phase output for a new or under-specified course."""

    target_audience: str = Field(default="")
    learner_context: str = Field(default="")
    prior_knowledge_assumptions: list[str] = Field(default_factory=list)
    learner_needs: list[str] = Field(default_factory=list)
    resource_constraints: list[str] = Field(default_factory=list)
    designer_requirements: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class ADDIEDesign(BaseModel):
    """Design phase output before downstream content development."""

    instructional_strategy: str = Field(default="")
    module_sequence_rationale: str = Field(default="")
    assessment_strategy: str = Field(default="")
    engagement_strategy: str = Field(default="")
    differentiation_strategy: str = Field(default="")
    success_criteria: list[str] = Field(default_factory=list)
    revision_notes: list[str] = Field(default_factory=list)


class ADDIEPlan(BaseModel):
    """The Analyze and Design phases of ADDIE captured for review."""

    analysis: ADDIEAnalysis = Field(default_factory=ADDIEAnalysis)
    design: ADDIEDesign = Field(default_factory=ADDIEDesign)


def _folder_title(module_title: str) -> str:
    title = module_title.strip()
    for separator in (" — ", " – ", " - "):
        if separator in title:
            title = title.split(separator, 1)[0].strip()
            break
    return title or module_title.strip()


def _build_packaging_plan(
    topic: str,
    modules: list[ModuleSpec],
) -> CoursePackagingPlan:
    module_count = len(modules)
    module_packages = []

    for index, module in enumerate(modules, start=1):
        folder_title = _folder_title(module.title)
        module_packages.append(
            ModulePackageSpec(
                module_id=module.module_id,
                module_index=index,
                module_title=module.title,
                folder_title=folder_title,
                folder_name=f"Module {index} - {folder_title}",
                slides_file=f"Module {index} - Slides.pptx",
                exercises_file=f"Module {index} - Exercises.pptx",
                questions_file=f"Module {index} - Questions.pptx",
                assignments_file=f"Module {index} - Assignments.pptx",
            )
        )

    return CoursePackagingPlan(
        bank_folders=[
            "Course Slides",
            "Exercise Bank",
            "Quiz Bank",
            "Assignment Bank",
            "Additional resources",
        ],
        component_banks=[
            ComponentBankSpec(
                folder_name="Specification",
                master_file=f"{topic} Three Level Information.pdf",
                per_module_unit="source module list",
                units_per_module=None,
                total_units=1,
                split_file_name="not split",
                split_by_module=False,
            ),
            ComponentBankSpec(
                folder_name="Course Slides",
                master_file=f"{topic}_Slides.pptx",
                per_module_unit="concept slides + practise handoff",
                units_per_module=None,
                total_units=None,
                split_file_name="Module N - Slides.pptx",
            ),
            ComponentBankSpec(
                folder_name="Exercise Bank",
                master_file=f"{topic} Exercises bank.pptx",
                per_module_unit="exercise slides",
                units_per_module=6,
                total_units=module_count * 6,
                split_file_name="Module N - Exercises.pptx",
            ),
            ComponentBankSpec(
                folder_name="Quiz Bank",
                master_file=f"{topic} Questions bank.pptx",
                per_module_unit="question and answer slide pairs",
                units_per_module=10,
                total_units=module_count * 10,
                split_file_name="Module N - Questions.pptx",
            ),
            ComponentBankSpec(
                folder_name="Assignment Bank",
                master_file="Assignments.pptx",
                per_module_unit="assignment slides",
                units_per_module=3,
                total_units=module_count * 3,
                split_file_name="Module N - Assignments.pptx",
            ),
            ComponentBankSpec(
                folder_name="Additional resources",
                master_file="folder",
                per_module_unit="notebooks, datasets, video, links",
                units_per_module=None,
                total_units=None,
                split_file_name="not split",
                split_by_module=False,
            ),
        ],
        module_packages=module_packages,
        relationships=[
            "Specification module list drives Course Slides, Exercise Bank, Quiz Bank, and Assignment Bank.",
            "Module index plus module title is the primary join key across all split outputs.",
            "Course Slides practise handoff references the Exercise Bank and Quiz Bank for the same module.",
            "Additional resources hold shared notebooks, datasets, videos, and links referenced by all banks.",
        ],
        validation_checklist=[
            "Specification exists and lists exactly the modules used by every bank.",
            "All four split banks contain the same Module N - <Title> subfolders.",
            "Each module subfolder contains exactly one split file of the correct type.",
            "Counts match the spec: 6 exercises, 10 quiz questions, and 3 assignments per module.",
            "Course Slides handoff figures match the actual Exercise and Quiz bank counts.",
            "Speaker notes are present on split Course Slides files.",
            "Each split deck opens without repair and starts on its module divider.",
            "Additional resources hold every dataset or notebook referenced by the banks.",
        ],
    )


class CourseSpec(BaseModel):
    """Agent A -> Agent B handoff object (Game Plan §4.1, extended)."""

    course_id: str
    subject: Subject
    age_bracket: AgeBracket
    topic: str
    planning_mode: PlanningMode = PlanningMode.FIXED_PEDAGOGY
    pedagogy: PedagogyConstraints
    relevancy_note: str = Field(
        default="",
        description="Agent A's check that the topic is still current (2 Jul meeting).",
    )
    references: list[Reference] = Field(default_factory=list)
    modules: list[ModuleSpec] = Field(..., min_length=1)
    overview: CourseOverview = Field(default_factory=CourseOverview)
    phases: list[CoursePhase] = Field(default_factory=list)
    packaging: CoursePackagingPlan = Field(default_factory=CoursePackagingPlan)
    addie: ADDIEPlan = Field(default_factory=ADDIEPlan)
    schema_version: str = "0.5.0"

    @model_validator(mode="after")
    def validate_prerequisite_graph(self) -> "CourseSpec":
        ids = [m.module_id for m in self.modules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate module_id in course spec")
        seen: set[str] = set()
        for m in self.modules:
            for p in m.prerequisites:
                if p not in ids:
                    raise ValueError(f"{m.module_id} lists unknown prerequisite '{p}'")
                if p == m.module_id:
                    raise ValueError(f"{m.module_id} lists itself as a prerequisite")
                if p not in seen:
                    raise ValueError(
                        f"{m.module_id} depends on '{p}' which appears later in the "
                        "sequence — modules must be topologically ordered"
                    )
            seen.add(m.module_id)
        return self

    @model_validator(mode="after")
    def validate_session_lengths(self) -> "CourseSpec":
        cap = self.pedagogy.max_session_min
        for m in self.modules:
            if m.target_minutes > cap:
                raise ValueError(
                    f"{m.module_id}: target_minutes={m.target_minutes} exceeds the "
                    f"tier-{self.pedagogy.tier} hard cap of {cap} min (T03 matrix)"
                )
        return self

    @model_validator(mode="after")
    def validate_phases(self) -> "CourseSpec":
        if not self.phases:
            return self

        module_ids = {m.module_id for m in self.modules}
        assigned: list[str] = []
        for phase in self.phases:
            for module_id in phase.module_ids:
                if module_id not in module_ids:
                    raise ValueError(
                        f"{phase.phase_id} lists unknown module_id '{module_id}'"
                    )
                assigned.append(module_id)

        if len(assigned) != len(set(assigned)):
            raise ValueError("duplicate module_id across phases")

        if set(assigned) != module_ids:
            missing = sorted(module_ids - set(assigned))
            raise ValueError(
                "phases must cover every module exactly once"
                + (f"; missing: {missing}" if missing else "")
            )

        return self

    @model_validator(mode="after")
    def derive_packaging_plan(self) -> "CourseSpec":
        self.packaging = _build_packaging_plan(self.topic, self.modules)
        return self
