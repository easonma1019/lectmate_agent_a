from agent_a import AgeBracket, PlanningMode, Subject
from agent_a.intake import run_intake, write_intake_request


def test_intake_asks_follow_up_when_required_fields_missing():
    result = run_intake(
        ["我想做一门项目制课程，先帮我聊清楚需求。"],
        use_llm=False,
    )

    assert not result.ready
    assert "subject" in result.missing_fields
    assert result.follow_up_questions


def test_intake_builds_course_request(tmp_path):
    result = run_intake(
        [
            "我想做一门 AI 课程，主题是 Data visualisation with Python，"
            "面向 14-17 岁学生，使用 addie 模式，最好项目制，8 个模块。"
        ],
        use_llm=False,
    )

    assert result.ready
    assert result.request is not None
    assert result.request.subject == Subject.AI
    assert result.request.age_bracket == AgeBracket.INNOVATORS
    assert result.request.planning_mode == PlanningMode.ADDIE_DISCOVERY
    assert result.request.max_modules == 8
    assert result.request.design_requirements

    output_path = write_intake_request(result, tmp_path / "course_request.json")
    assert output_path.exists()
