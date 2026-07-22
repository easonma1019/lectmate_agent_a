from agent_a import AgeBracket, PlanningMode, Subject
from agent_a.intake import _parse_intake_payload, run_intake, write_intake_request


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


def test_intake_parser_accepts_null_optional_lists():
    result = _parse_intake_payload(
        {
            "summary": "Python course for a 9-year-old learner.",
            "missing_fields": None,
            "follow_up_questions": None,
            "confidence": "medium",
            "course_request": {
                "subject": "Coding",
                "age_bracket": "Explorers (6-9)",
                "topic": "Python fundamentals",
                "learning_objectives": None,
                "design_requirements": None,
                "max_modules": None,
                "planning_mode": "fixed",
                "source": "intake_chatbot",
            },
        }
    )

    assert result.ready
    assert result.request is not None
    assert result.request.learning_objectives == []
    assert result.request.design_requirements == []
    assert result.missing_fields == []
    assert result.follow_up_questions == []


def test_intake_guardrail_recovers_chinese_single_age(monkeypatch):
    def fake_llm(_prompt: str) -> str:
        return """
        {
          "summary": "User wants to create a Python course for about 9 children.",
          "missing_fields": ["age_bracket"],
          "follow_up_questions": ["What age bracket is the course for?"],
          "confidence": "medium",
          "course_request": null
        }
        """

    monkeypatch.setattr("agent_a.intake._call_llm", fake_llm)

    result = run_intake(
        ["我想做一门python课程，大概9岁的孩子"],
        use_llm=True,
    )

    assert result.ready
    assert result.request is not None
    assert result.request.subject == Subject.CODING
    assert result.request.age_bracket == AgeBracket.EXPLORERS
    assert result.request.topic == "Python fundamentals"
    assert result.missing_fields == []
    assert result.follow_up_questions == []
