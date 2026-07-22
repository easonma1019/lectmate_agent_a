from agent_a import AgeBracket, CourseRequest, Subject, plan_course
from agent_a.reviser import (
    load_course_spec,
    revise_course_spec,
    write_course_spec_json,
    write_revision_report,
)


def test_revision_flow_updates_spec_and_report(tmp_path):
    old_spec = plan_course(
        CourseRequest(
            subject=Subject.CODING,
            age_bracket=AgeBracket.CREATORS,
            topic="Python fundamentals",
            max_modules=3,
        ),
        use_llm=False,
    )

    old_path = write_course_spec_json(old_spec, tmp_path / "spec.json")
    loaded = load_course_spec(old_path)
    result = revise_course_spec(
        loaded,
        "把课程改成 5 个模块，并加强项目制学习",
        use_llm=False,
        use_llm_reviewer=False,
        html_path=tmp_path / "review_v2.html",
    )

    assert result.passed
    assert len(result.new_spec.modules) == 5
    assert len(result.new_spec.packaging.module_packages) == 5
    assert result.new_spec.packaging.component_banks[2].total_units == 30
    assert result.html_path is not None
    assert result.html_path.exists()
    assert result.reviewer.passed
    assert any("Modules: 3 -> 5" in item for item in result.diff_summary)

    report_path = write_revision_report(result, tmp_path / "revision_report.md")
    report = report_path.read_text(encoding="utf-8")
    assert "Overall: PASS" in report
    assert "LLM Reviewer" in report
    assert "Requested module count" in report
