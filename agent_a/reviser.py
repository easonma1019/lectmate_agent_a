"""Revision workflow for existing CourseSpec JSON files."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .html_report import render_course_spec_html, write_course_spec_html
from .planner import _call_llm, _parse_json, rule_check
from .schemas import CourseSpec, ModuleSpec


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


@dataclass
class ReviewerResult:
    passed: bool
    summary: str
    evidence: list[str] = field(default_factory=list)
    concerns: list[str] = field(default_factory=list)
    suggested_revision: str = ""


@dataclass
class RevisionResult:
    old_spec: CourseSpec
    new_spec: CourseSpec
    change_request: str
    structure_checks: list[CheckResult]
    intent_checks: list[CheckResult]
    html_checks: list[CheckResult]
    diff_summary: list[str]
    reviewer: ReviewerResult
    html_path: Path | None = None

    @property
    def passed(self) -> bool:
        checks = self.structure_checks + self.intent_checks + self.html_checks
        return all(check.passed for check in checks) and self.reviewer.passed


def load_course_spec(path: str | Path) -> CourseSpec:
    return CourseSpec.model_validate_json(
        Path(path).read_text(encoding="utf-8")
    )


def write_course_spec_json(spec: CourseSpec, path: str | Path) -> Path:
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        spec.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path.resolve()


def _requested_module_count(change_request: str) -> int | None:
    patterns = [
        r"(\d+)\s*(?:个)?\s*(?:modules?|模块)",
        r"(?:modules?|模块)\s*(?:改成|变成|to)?\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, change_request, re.IGNORECASE)
        if match:
            return int(match.group(1))
    return None


def _mentions_project_based(change_request: str) -> bool:
    lowered = change_request.lower()
    return any(
        keyword in lowered
        for keyword in [
            "project",
            "portfolio",
            "项目",
            "作品集",
            "项目制",
            "pbl",
        ]
    )


def _module_template(old_spec: CourseSpec, module_index: int) -> ModuleSpec:
    previous_id = f"m{module_index - 1}" if module_index > 1 else None
    exercise_type = old_spec.pedagogy.exercise_types[0]
    target_minutes = min(
        old_spec.pedagogy.max_session_min,
        old_spec.modules[-1].target_minutes if old_spec.modules else 30,
    )
    return ModuleSpec(
        module_id=f"m{module_index}",
        title=f"Applied project step {module_index}",
        objective=f"Apply course concept {module_index} in the project",
        prerequisites=[previous_id] if previous_id else [],
        target_minutes=target_minutes,
        exercise_type=exercise_type,
        csta_alignment=old_spec.pedagogy.key_csta_standards[:1],
    )


def _stub_revise(old_spec: CourseSpec, change_request: str) -> CourseSpec:
    requested_count = _requested_module_count(change_request)
    modules = [
        module.model_copy(deep=True)
        for module in old_spec.modules
    ]

    if requested_count is not None:
        if requested_count < len(modules):
            modules = modules[:requested_count]
        else:
            for index in range(len(modules) + 1, requested_count + 1):
                modules.append(_module_template(old_spec, index))

        for index, module in enumerate(modules, start=1):
            module.module_id = f"m{index}"
            module.prerequisites = [f"m{index - 1}"] if index > 1 else []

    overview = old_spec.overview.model_copy(deep=True)
    addie = old_spec.addie.model_copy(deep=True)

    if _mentions_project_based(change_request):
        overview.what_you_will_build = (
            "Learners build a portfolio-ready project across the modules, "
            "using each new concept as one step toward the final artifact."
        )
        if "Project-Based Learning" not in overview.skill_tags:
            overview.skill_tags.append("Project-Based Learning")
        overview.progress_tracking = [
            *overview.progress_tracking,
            "Project checkpoints are reviewed throughout the course.",
        ]
        addie.design.instructional_strategy = (
            "Use project-based learning: each module contributes a visible "
            "piece of the final portfolio artifact."
        )
        addie.design.revision_notes = [
            *addie.design.revision_notes,
            "Revision request emphasized project-based learning.",
        ]

    addie.design.revision_notes = [
        *addie.design.revision_notes,
        f"Revision request: {change_request}",
    ]

    phases = []
    phase_count = min(3, len(modules))
    for phase_index in range(phase_count):
        start = (phase_index * len(modules)) // phase_count + 1
        end = ((phase_index + 1) * len(modules)) // phase_count
        phases.append(
            {
                "phase_id": f"p{phase_index + 1}",
                "title": old_spec.phases[phase_index].title
                if phase_index < len(old_spec.phases)
                else f"Phase {phase_index + 1}",
                "module_ids": [
                    f"m{module_index}"
                    for module_index in range(start, end + 1)
                ],
            }
        )

    return CourseSpec.model_validate(
        {
            **old_spec.model_dump(),
            "modules": [module.model_dump() for module in modules],
            "overview": overview.model_dump(),
            "phases": phases,
            "addie": addie.model_dump(),
        }
    )


def _revision_prompt(old_spec: CourseSpec, change_request: str) -> str:
    return f"""You are revising an existing LectMate CourseSpec.

CHANGE REQUEST:
{change_request}

RULES:
- Read the old CourseSpec carefully.
- Return a complete revised CourseSpec JSON object, not a patch.
- Preserve fields that are still valid.
- Update modules, phases, overview, addie, references, and relevancy_note when
  the change request implies they should change.
- Keep module_id values sequential: m1, m2, ...
- Keep prerequisites valid and only pointing to earlier modules.
- Keep phases covering every module exactly once.
- Keep target_minutes within the existing pedagogy max_session_min.
- Do not invent packaging; it is derived by code from modules.
- Return JSON only. No markdown fences.

OLD COURSESPEC:
{old_spec.model_dump_json(indent=2)}
"""


def _llm_revise(old_spec: CourseSpec, change_request: str) -> CourseSpec:
    revised = _parse_json(_call_llm(_revision_prompt(old_spec, change_request)))
    if not isinstance(revised, dict):
        raise ValueError("Revision response must be a JSON object.")
    return CourseSpec.model_validate(revised)


def _structure_checks(spec: CourseSpec) -> list[CheckResult]:
    problems = rule_check(spec)
    return [
        CheckResult("CourseSpec schema", True, "CourseSpec loaded successfully."),
        CheckResult(
            "Rule validation",
            not problems,
            "No rule violations." if not problems else "; ".join(problems),
        ),
        CheckResult(
            "Phase coverage",
            bool(spec.phases),
            f"{len(spec.phases)} phase(s) cover {len(spec.modules)} module(s).",
        ),
        CheckResult(
            "Packaging derived",
            len(spec.packaging.module_packages) == len(spec.modules),
            f"{len(spec.packaging.module_packages)} module package(s).",
        ),
    ]


def _intent_checks(
    old_spec: CourseSpec,
    new_spec: CourseSpec,
    change_request: str,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    requested_count = _requested_module_count(change_request)
    if requested_count is not None:
        checks.append(
            CheckResult(
                "Requested module count",
                len(new_spec.modules) == requested_count,
                f"{len(old_spec.modules)} -> {len(new_spec.modules)} module(s); requested {requested_count}.",
            )
        )

    if _mentions_project_based(change_request):
        searchable = json.dumps(
            {
                "overview": new_spec.overview.model_dump(),
                "addie": new_spec.addie.model_dump(),
            },
            ensure_ascii=False,
        ).lower()
        has_project_signal = any(
            keyword in searchable
            for keyword in [
                "project",
                "portfolio",
                "项目",
                "作品集",
                "pbl",
            ]
        )
        checks.append(
            CheckResult(
                "Project-based learning signal",
                has_project_signal,
                "Project/portfolio language found in overview or ADDIE."
                if has_project_signal
                else "No clear project/portfolio signal found.",
            )
        )

    if not checks:
        checks.append(
            CheckResult(
                "Explicit intent rules",
                True,
                "No simple rule-based intent check was inferred; LLM reviewer is authoritative.",
            )
        )
    return checks


def _diff_summary(old_spec: CourseSpec, new_spec: CourseSpec) -> list[str]:
    summary = [
        f"Modules: {len(old_spec.modules)} -> {len(new_spec.modules)}",
        f"Phases: {len(old_spec.phases)} -> {len(new_spec.phases)}",
        (
            "Exercise Bank total: "
            f"{old_spec.packaging.component_banks[2].total_units} -> "
            f"{new_spec.packaging.component_banks[2].total_units}"
        ),
        (
            "Quiz Bank total: "
            f"{old_spec.packaging.component_banks[3].total_units} -> "
            f"{new_spec.packaging.component_banks[3].total_units}"
        ),
        (
            "Assignment Bank total: "
            f"{old_spec.packaging.component_banks[4].total_units} -> "
            f"{new_spec.packaging.component_banks[4].total_units}"
        ),
    ]

    old_titles = [module.title for module in old_spec.modules]
    new_titles = [module.title for module in new_spec.modules]
    added = new_titles[len(old_titles):]
    if added:
        summary.append("Added modules: " + ", ".join(added))

    renamed = []
    for index, (old_title, new_title) in enumerate(zip(old_titles, new_titles), start=1):
        if old_title != new_title:
            renamed.append(f"m{index}: {old_title} -> {new_title}")
    if renamed:
        summary.append("Renamed modules: " + "; ".join(renamed))

    return summary


def _html_checks(spec: CourseSpec, html: str) -> list[CheckResult]:
    missing_titles = [
        module.title
        for module in spec.modules
        if module.title not in html
    ]
    required_sections = [
        "Level A - Landing Page Card",
        "Level B - Course Overview Page (Pre-Login)",
        "Level C - Full Course Page (Post-Login)",
        "ADDIE Analysis & Design",
        "Automation Packaging",
    ]
    missing_sections = [
        section
        for section in required_sections
        if section not in html
    ]
    return [
        CheckResult(
            "HTML module titles",
            not missing_titles,
            "All module titles are present."
            if not missing_titles
            else "Missing: " + ", ".join(missing_titles),
        ),
        CheckResult(
            "HTML required sections",
            not missing_sections,
            "All required sections are present."
            if not missing_sections
            else "Missing: " + ", ".join(missing_sections),
        ),
    ]


def _reviewer_prompt(
    old_spec: CourseSpec,
    new_spec: CourseSpec,
    change_request: str,
    diff_summary: list[str],
    structure_checks: list[CheckResult],
    intent_checks: list[CheckResult],
) -> str:
    checks = [
        {
            "name": check.name,
            "passed": check.passed,
            "detail": check.detail,
        }
        for check in structure_checks + intent_checks
    ]
    payload: dict[str, Any] = {
        "change_request": change_request,
        "diff_summary": diff_summary,
        "checks": checks,
        "old_spec": old_spec.model_dump(),
        "new_spec": new_spec.model_dump(),
    }
    return f"""You are the reviewer in a curriculum revision loop.

Decide whether the new CourseSpec satisfies the user's change request.
Use the programmatic checks as evidence, but also judge semantic intent.

Return ONLY this JSON object:
{{
  "passed": true,
  "summary": "...",
  "evidence": ["...", "..."],
  "concerns": ["...", "..."],
  "suggested_revision": ""
}}

If the revision does not satisfy the request, set "passed": false and write a
specific suggested_revision instruction for the next attempt.

REVIEW PAYLOAD:
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""


def _stub_reviewer(
    structure_checks: list[CheckResult],
    intent_checks: list[CheckResult],
    diff_summary: list[str],
) -> ReviewerResult:
    failed = [
        check
        for check in structure_checks + intent_checks
        if not check.passed
    ]
    return ReviewerResult(
        passed=not failed,
        summary=(
            "Rule-based reviewer passed the revision."
            if not failed
            else "Rule-based reviewer found failed checks."
        ),
        evidence=diff_summary,
        concerns=[f"{check.name}: {check.detail}" for check in failed],
        suggested_revision=(
            ""
            if not failed
            else "Revise again and address the failed checks exactly."
        ),
    )


def _llm_reviewer(
    old_spec: CourseSpec,
    new_spec: CourseSpec,
    change_request: str,
    diff_summary: list[str],
    structure_checks: list[CheckResult],
    intent_checks: list[CheckResult],
) -> ReviewerResult:
    raw = _call_llm(
        _reviewer_prompt(
            old_spec,
            new_spec,
            change_request,
            diff_summary,
            structure_checks,
            intent_checks,
        )
    )
    parsed = _parse_json(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Reviewer response must be a JSON object.")
    return ReviewerResult(
        passed=bool(parsed.get("passed")),
        summary=str(parsed.get("summary", "")),
        evidence=[
            str(item)
            for item in parsed.get("evidence", [])
        ],
        concerns=[
            str(item)
            for item in parsed.get("concerns", [])
        ],
        suggested_revision=str(parsed.get("suggested_revision", "")),
    )


def _review_revision(
    old_spec: CourseSpec,
    new_spec: CourseSpec,
    change_request: str,
    diff_summary: list[str],
    structure_checks: list[CheckResult],
    intent_checks: list[CheckResult],
    use_llm_reviewer: bool,
) -> ReviewerResult:
    if not use_llm_reviewer:
        return _stub_reviewer(structure_checks, intent_checks, diff_summary)
    return _llm_reviewer(
        old_spec,
        new_spec,
        change_request,
        diff_summary,
        structure_checks,
        intent_checks,
    )


def revise_course_spec(
    old_spec: CourseSpec,
    change_request: str,
    use_llm: bool = True,
    use_llm_reviewer: bool = True,
    max_rounds: int = 1,
    html_path: str | Path | None = None,
) -> RevisionResult:
    """Revise an existing CourseSpec and verify the result."""

    current_change = change_request
    last_result: RevisionResult | None = None
    rounds = max(1, max_rounds)

    for _ in range(rounds):
        new_spec = (
            _llm_revise(old_spec, current_change)
            if use_llm
            else _stub_revise(old_spec, current_change)
        )

        structure_checks = _structure_checks(new_spec)
        intent_checks = _intent_checks(old_spec, new_spec, change_request)
        diff_summary = _diff_summary(old_spec, new_spec)
        html = render_course_spec_html(new_spec)
        html_checks = _html_checks(new_spec, html)
        reviewer = _review_revision(
            old_spec,
            new_spec,
            change_request,
            diff_summary,
            structure_checks,
            intent_checks,
            use_llm_reviewer,
        )
        written_html_path = (
            write_course_spec_html(new_spec, html_path)
            if html_path is not None
            else None
        )
        last_result = RevisionResult(
            old_spec=old_spec,
            new_spec=new_spec,
            change_request=change_request,
            structure_checks=structure_checks,
            intent_checks=intent_checks,
            html_checks=html_checks,
            diff_summary=diff_summary,
            reviewer=reviewer,
            html_path=written_html_path,
        )

        if last_result.passed or not reviewer.suggested_revision:
            return last_result
        current_change = (
            change_request
            + "\n\nReviewer requested another revision:\n"
            + reviewer.suggested_revision
        )

    assert last_result is not None
    return last_result


def _format_checks(checks: list[CheckResult]) -> str:
    lines = []
    for check in checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"- {status}: {check.name} - {check.detail}")
    return "\n".join(lines)


def render_revision_report(result: RevisionResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    reviewer_status = "PASS" if result.reviewer.passed else "FAIL"
    html_line = (
        f"\nHTML: {result.html_path.as_uri()}\n"
        if result.html_path is not None
        else ""
    )
    return f"""# Revision Report

Overall: {status}
{html_line}
## Change Request

{result.change_request}

## Structure Validation

{_format_checks(result.structure_checks)}

## Intent Validation

{_format_checks(result.intent_checks)}

## HTML Validation

{_format_checks(result.html_checks)}

## Diff Summary

{chr(10).join(f"- {item}" for item in result.diff_summary)}

## LLM Reviewer

Reviewer: {reviewer_status}

Summary: {result.reviewer.summary}

Evidence:
{chr(10).join(f"- {item}" for item in result.reviewer.evidence) or "- None"}

Concerns:
{chr(10).join(f"- {item}" for item in result.reviewer.concerns) or "- None"}

Suggested revision:
{result.reviewer.suggested_revision or "None"}
"""


def write_revision_report(
    result: RevisionResult,
    path: str | Path,
) -> Path:
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_revision_report(result),
        encoding="utf-8",
    )
    return output_path.resolve()
