"""Course-design intake chatbot helpers.

The intake layer turns a natural-language conversation with a curriculum
designer into a structured CourseRequest. It intentionally stops before course
generation, so the designer can confirm the request first.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .planner import _call_llm, _parse_json
from .schemas import AgeBracket, CourseRequest, PlanningMode, Subject


@dataclass
class IntakeResult:
    request: CourseRequest | None
    summary: str
    missing_fields: list[str]
    follow_up_questions: list[str]
    confidence: str

    @property
    def ready(self) -> bool:
        return self.request is not None and not self.missing_fields


def _enum_values(enum_cls) -> list[str]:
    return [item.value for item in enum_cls]


def _infer_subject(text: str) -> Subject | None:
    lowered = text.lower()
    explicit_patterns = [
        (Subject.AI, ["ai 课程", "ai课", "人工智能课程", "人工智能课"]),
        (Subject.CODING, ["coding 课程", "编程课程", "编程课"]),
        (Subject.FINANCIAL_LITERACY, ["financial literacy", "金融课程", "财商课程"]),
        (Subject.ENTREPRENEURSHIP, ["entrepreneurship", "创业课程"]),
    ]
    for subject, keywords in explicit_patterns:
        if any(keyword in lowered for keyword in keywords):
            return subject

    candidates = {
        Subject.AI: ["ai", "artificial intelligence", "machine learning", "人工智能"],
        Subject.CODING: ["coding", "python", "programming", "code", "编程"],
        Subject.FINANCIAL_LITERACY: ["financial", "finance", "money", "金融", "财商"],
        Subject.ENTREPRENEURSHIP: ["entrepreneur", "startup", "business", "创业"],
    }
    for subject, keywords in candidates.items():
        if any(keyword in lowered for keyword in keywords):
            return subject
    return None


def _infer_age(text: str) -> AgeBracket | None:
    match = re.search(r"(\d{1,2})\s*[-~到至]\s*(\d{1,2})", text)
    if match:
        low = int(match.group(1))
        high = int(match.group(2))
        if low >= 6 and high <= 9:
            return AgeBracket.EXPLORERS
        if low >= 10 and high <= 13:
            return AgeBracket.CREATORS
        if low >= 14 and high <= 17:
            return AgeBracket.INNOVATORS
        if low >= 18 and high <= 21:
            return AgeBracket.LEADERS

    single = re.search(r"(\d{1,2})\s*(?:岁|years?\s*old|yo)", text, re.IGNORECASE)
    if single:
        age = int(single.group(1))
        if 6 <= age <= 9:
            return AgeBracket.EXPLORERS
        if 10 <= age <= 13:
            return AgeBracket.CREATORS
        if 14 <= age <= 17:
            return AgeBracket.INNOVATORS
        if 18 <= age <= 21:
            return AgeBracket.LEADERS

    lowered = text.lower()
    for age in AgeBracket:
        if age.value.lower() in lowered or age.name.lower() in lowered:
            return age
    return None


def _infer_mode(text: str) -> PlanningMode:
    lowered = text.lower()
    if any(keyword in lowered for keyword in ["addie", "探索", "全新", "沟通", "澄清"]):
        return PlanningMode.ADDIE_DISCOVERY
    return PlanningMode.FIXED_PEDAGOGY


def _infer_module_count(text: str) -> int | None:
    patterns = [
        r"(\d+)\s*(?:个)?\s*(?:modules?|模块)",
        r"(?:modules?|模块)\s*(?:数量)?\s*(?:为|是|=|:)?\s*(\d+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 20:
                return value
    return None


def _heuristic_topic(text: str) -> str:
    lowered = text.lower()
    if "python" in lowered:
        return "Python fundamentals"

    quoted = re.findall(r"[\"'“”‘’]([^\"'“”‘’]{3,80})[\"'“”‘’]", text)
    if quoted:
        return quoted[0].strip()

    patterns = [
        r"(?:topic|主题|课程主题|课程)\s*(?:是|为|:|：)?\s*([^。\n,，]{3,80})",
        r"(?:on|about|关于)\s+([^。\n,，]{3,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _heuristic_intake(transcript: str) -> IntakeResult:
    subject = _infer_subject(transcript)
    age = _infer_age(transcript)
    topic = _heuristic_topic(transcript)
    mode = _infer_mode(transcript)
    modules = _infer_module_count(transcript)

    missing = []
    questions = []
    if subject is None:
        missing.append("subject")
        questions.append(
            "这门课属于哪个方向：Coding、AI、Financial Literacy，还是 Entrepreneurship？"
        )
    if age is None:
        missing.append("age_bracket")
        questions.append(
            "目标学生年龄段是哪一组：6-9、10-13、14-17，还是 18-21？"
        )
    if not topic:
        missing.append("topic")
        questions.append("这门课的主题或暂定课程名是什么？")

    request = None
    if subject is not None and age is not None and topic:
        requirements = []
        if any(keyword in transcript.lower() for keyword in ["project", "portfolio", "项目", "作品集"]):
            requirements.append("Prefer project-based learning and portfolio-ready outputs.")
        request = CourseRequest(
            subject=subject,
            age_bracket=age,
            topic=topic,
            max_modules=modules,
            planning_mode=mode,
            design_requirements=requirements,
            source="intake_chatbot",
        )

    return IntakeResult(
        request=request,
        summary="Heuristic intake summary from the current transcript.",
        missing_fields=missing,
        follow_up_questions=questions,
        confidence="low" if missing else "medium",
    )


def _intake_prompt(transcript: str) -> str:
    return f"""You are the intake chatbot for LectMate Agent A.

Your job is to convert a conversation with a curriculum designer into a
structured CourseRequest draft. Do not design the full course.

Allowed subjects: {_enum_values(Subject)}
Allowed age brackets: {_enum_values(AgeBracket)}
Allowed planning modes: {_enum_values(PlanningMode)}

Choose planning_mode:
- "fixed" if the designer already has clear pedagogy/constraints and mainly
  wants the existing course-structure generator.
- "addie" if the course is new, ambiguous, or needs Analyze/Design discovery.

Return ONLY this JSON object:
{{
  "summary": "...",
  "missing_fields": ["subject", "age_bracket", "topic"],
  "follow_up_questions": ["...", "..."],
  "confidence": "low|medium|high",
  "course_request": {{
    "subject": "Coding",
    "age_bracket": "Creators (10-13)",
    "topic": "...",
    "learning_objectives": ["...", "..."],
    "design_requirements": ["...", "..."],
    "max_modules": null,
    "planning_mode": "fixed",
    "source": "intake_chatbot"
  }}
}}

If a required field is missing, set course_request to null and ask concise
follow-up questions.

CONVERSATION TRANSCRIPT:
{transcript}
"""


def _parse_intake_payload(payload: dict) -> IntakeResult:
    request_payload = payload.get("course_request")
    request = (
        CourseRequest(**request_payload)
        if isinstance(request_payload, dict)
        else None
    )
    return IntakeResult(
        request=request,
        summary=str(payload.get("summary", "")),
        missing_fields=[
            str(item)
            for item in payload.get("missing_fields", [])
        ],
        follow_up_questions=[
            str(item)
            for item in payload.get("follow_up_questions", [])
        ],
        confidence=str(payload.get("confidence", "low")),
    )


def run_intake(
    messages: list[str],
    use_llm: bool = True,
) -> IntakeResult:
    transcript = "\n".join(messages)
    if not use_llm:
        return _heuristic_intake(transcript)

    parsed = _parse_json(_call_llm(_intake_prompt(transcript)))
    if not isinstance(parsed, dict):
        raise ValueError("Intake response must be a JSON object.")
    return _parse_intake_payload(parsed)


def write_intake_request(
    result: IntakeResult,
    path: str | Path,
) -> Path:
    if result.request is None:
        raise ValueError("Cannot write CourseRequest because intake is incomplete.")
    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        result.request.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return output_path.resolve()


def render_intake_summary(result: IntakeResult) -> str:
    payload = {
        "ready": result.ready,
        "confidence": result.confidence,
        "summary": result.summary,
        "missing_fields": result.missing_fields,
        "follow_up_questions": result.follow_up_questions,
        "course_request": (
            json.loads(result.request.model_dump_json())
            if result.request is not None
            else None
        ),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
