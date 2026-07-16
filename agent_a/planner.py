"""
Agent A — Curriculum Architect planner.

Two-stage, constraint-based planning (Game Plan §5 'Techniques worth trying'):

  Stage 0  Age-tier lookup (T03 matrix) -> pedagogy constraints
  Stage 1  LLM proposes a high-level module list (titles + concepts only)
  Stage 2  LLM expands each module into objective / prerequisites / minutes,
           with the tier constraints and CSTA anchors injected in the prompt
  Stage 3  Rule validation (schema + concept graph + tier caps); on failure,
           one repair round with the violations fed back to the model.

Runs in two modes:

  - LLM mode:
        OPENROUTER_API_KEY is set -> real LLM planning through OpenRouter

  - Stub mode:
        no API key -> deterministic template output, so Agents B & C can
        integrate against a valid CourseSpec without calling an LLM
        (Game Plan §9: 'build against a stub').
"""

from __future__ import annotations

import json
import os
import re
import uuid

from dotenv import load_dotenv
from openai import OpenAI

from . import pedagogy
from .concept_graph import PYTHON_CONCEPTS, toposort_check
from .schemas import (
    CourseRequest,
    CourseSpec,
    ModuleSpec,
    Reference,
)


# ---------------------------------------------------------------------------
# OpenRouter configuration
# ---------------------------------------------------------------------------

# 读取项目目录中的 .env 文件
load_dotenv()

# 默认使用 OpenRouter 的免费模型路由器。
#
# 也可以在 .env 中使用 OPENROUTER_MODEL 指定其他模型，
# 例如：
#
# OPENROUTER_MODEL='openai/gpt-oss-20b:free'
#
# 如果没有设置 OPENROUTER_MODEL，就自动使用 openrouter/free。
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL",
    "openrouter/free",
)

# 缓存 OpenRouter 客户端。
#
# 初始值为 None，表示客户端还没有被创建。
# 只有真正需要调用 LLM 时，程序才会创建客户端。
_openrouter_client: OpenAI | None = None


def _get_openrouter_client() -> OpenAI:
    """Create and cache an OpenRouter client.

    The client is created only when the LLM is actually used. This means
    stub mode can still run without an API key.
    """

    global _openrouter_client

    # 如果客户端已经创建过，直接重复使用
    if _openrouter_client is not None:
        return _openrouter_client

    # 从环境变量读取 OpenRouter API Key
    api_key = os.environ.get("OPENROUTER_API_KEY")

    # use_llm=True 但没有配置密钥时，给出清晰错误
    if api_key is None:
        raise RuntimeError(
            "未读取到 OPENROUTER_API_KEY。"
            "请检查项目目录中的 .env 文件配置。"
        )

    # 防止用户把空字符串配置成 API Key
    if not api_key.strip():
        raise RuntimeError(
            "OPENROUTER_API_KEY 是空字符串，"
            "请检查项目目录中的 .env 文件配置。"
        )

    # OpenRouter 与 OpenAI API 兼容，
    # 因此可以使用 OpenAI 官方 Python SDK
    _openrouter_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    return _openrouter_client


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

def _constraints_block(req: CourseRequest, ped) -> str:
    """Build the age-tier constraint section used in the LLM prompts."""

    return f"""AGE TIER CONSTRAINTS (non-negotiable, from the T03 Content Design Matrix):
- Tier {ped.tier} — {req.age_bracket.value}; cognitive frame: {ped.cognitive_theory}
- CSTA anchor level: {ped.csta_level}; align modules to standards such as {", ".join(ped.key_csta_standards)}
- Raw text code allowed: {ped.raw_text_code_allowed}
- Content format: {ped.content_format}; metaphor/story: {ped.metaphor_story}
- Allowed exercise types (choose per module): {", ".join(ped.exercise_types)}
- Session hard cap: {ped.max_session_min} minutes per module — NEVER exceed this.
- Mini-project style for the course finale: {ped.mini_project_type}"""


def _stage1_prompt(
    req: CourseRequest,
    ped,
    n_modules: int,
) -> str:
    """Create the Stage 1 prompt for generating a course outline."""

    known = ", ".join(PYTHON_CONCEPTS.keys())

    return f"""You are the Curriculum Architect agent in a course-generation pipeline for a live 1-to-1 tutoring company. You plan course structure only — you never write teaching content.

COURSE REQUEST:
- Subject: {req.subject.value}
- Topic: {req.topic}
- Age bracket: {req.age_bracket.value}
- Requester objectives: {req.learning_objectives or "none given — derive sensible ones"}

{_constraints_block(req, ped)}

TASK (stage 1 of 2): propose a high-level module list of exactly {n_modules} modules for this course, in teaching order. For each module give ONLY a short title and the core concept it covers. Where a concept matches one of these canonical concept ids, use that id verbatim: {known}. Otherwise invent a short snake_case id.

Ordering rule: a concept must never be scheduled before the concepts it depends on.

Respond with ONLY a JSON array, no prose, no markdown fences:
[{{"title": "...", "concept": "snake_case_id"}}, ...]"""


def _stage2_prompt(
    req: CourseRequest,
    ped,
    outline: list[dict],
) -> str:
    """Create the Stage 2 prompt for expanding the course outline."""

    return f"""You are the Curriculum Architect agent. Stage 2: expand the agreed outline into a full course spec.

            COURSE REQUEST:
            - Subject: {req.subject.value}
            - Topic: "{req.topic}"
            - Age bracket: {req.age_bracket.value}

            AGREED OUTLINE (do not reorder, do not add or remove modules):
            {json.dumps(outline, indent=2)}

            {_constraints_block(req, ped)}

            For each module produce:
            - "module_id": "m1", "m2", ... in order
            - "title": from the outline (you may polish wording)
            - "objective": EXACTLY ONE clear, assessable learning objective
            (one verb, one outcome; no "and" joining two skills; no semicolons)
            - "prerequisites": list only the direct earlier module_ids this module 
            immediately builds on. Do not list every previous module.
            - "target_minutes": integer <= {ped.max_session_min},
            realistic for one live session
            - "exercise_type": exactly one value from {ped.exercise_types}
            - "csta_alignment": 1-2 CSTA standard codes from
            {ped.key_csta_standards}

            Also produce:
            - "relevancy_note": 2-3 sentences on whether "{req.topic}" is current
            and worth teaching in 2026 for this age bracket, noting anything
            outdated to avoid.
            - "references": 2-4 grounding sources, such as curriculum standards,
            well-known textbooks or official documentation. Each reference must
            be an object with:
            {{"title", "kind", "identifier"}}

            The "kind" field must be one of:
            - "standard"
            - "textbook"
            - "web"
            - "paper"

            Respond with ONLY a JSON object, no prose, no markdown fences:
            {{"relevancy_note": "...", "references": [...], "modules": [...]}}"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------

def _call_llm(prompt: str) -> str:
    """Send a prompt to an LLM through OpenRouter.

    By default, OpenRouter automatically selects an available free model
    because OPENROUTER_MODEL defaults to "openrouter/free".
    """

    client = _get_openrouter_client()

    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a curriculum-planning assistant. "
                        "Follow all formatting and schema instructions exactly. "
                        "When asked for JSON, return valid JSON only. "
                        "Do not use Markdown code fences and do not add explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            # 课程结构和 JSON 输出需要稳定，避免随机性太高
            temperature=0.2,

            # 对应旧 Anthropic 代码中的 max_tokens=4000
            max_tokens=4000,
        )

    except Exception as exc:
        raise RuntimeError(
            f"OpenRouter API 请求失败：{exc}"
        ) from exc

    # 正常响应至少应该有一个 choice
    if not response.choices:
        raise RuntimeError(
            "OpenRouter API 未返回任何候选回答。"
        )

    content = response.choices[0].message.content

    # 某些异常请求可能返回空内容
    if content is None or not content.strip():
        raise RuntimeError(
            "OpenRouter API 返回了空内容。"
        )

    return content


# ---------------------------------------------------------------------------
# JSON parsing
# ---------------------------------------------------------------------------

def _parse_json(text: str):
    """Extract and parse JSON returned by the LLM.

    The prompts request JSON only, but some free models may still add
    Markdown fences or a short explanation. This function attempts to
    remove that extra formatting before calling json.loads().
    """

    if not isinstance(text, str):
        raise TypeError(
            f"LLM response must be a string, received {type(text).__name__}."
        )

    text = text.strip()

    if not text:
        raise ValueError(
            "Cannot parse JSON because the LLM response is empty."
        )

    # 去除 ```json 和 ``` 代码块标记
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    # 找到第一个 JSON 数组或对象的起点
    array_start = text.find("[")
    object_start = text.find("{")

    possible_starts = [
        index
        for index in (array_start, object_start)
        if index >= 0
    ]

    if not possible_starts:
        raise ValueError(
            "LLM response did not contain a JSON object or JSON array.\n"
            f"Response preview: {text[:300]}"
        )

    start = min(possible_starts)
    json_text = text[start:]

    # 先尝试直接解析
    try:
        return json.loads(json_text)

    except json.JSONDecodeError as first_error:
        # 部分模型可能在 JSON 后面添加一句解释。
        # 使用 JSONDecoder.raw_decode 只读取第一个完整 JSON 值。
        try:
            decoder = json.JSONDecoder()
            result, _ = decoder.raw_decode(json_text)
            return result

        except json.JSONDecodeError as second_error:
            raise ValueError(
                "OpenRouter returned content that could not be parsed "
                "as valid JSON.\n"
                f"Response preview: {text[:500]}"
            ) from second_error


# ---------------------------------------------------------------------------
# Validation beyond the schema
# ---------------------------------------------------------------------------

def rule_check(
    spec: CourseSpec,
    outline_concepts: list[str] | None = None,
) -> list[str]:
    """Run second-pass rule validation.

    Returns:
        A list of violation messages. An empty list means validation passed.

    Pydantic already enforces schema shape, prerequisite topology and the
    tier session cap. This function adds pedagogy-quality rules.
    """

    problems: list[str] = []

    # 单一学习目标检查
    #
    # 如果 objective 出现多个 "and"，可能同时包含多个学习目标
    for module in spec.modules:
        if re.search(r"\band\b", module.objective, re.IGNORECASE):
            words = module.objective.lower().split()

            if words.count("and") >= 2:
                problems.append(
                    f"{module.module_id}: objective likely compound: "
                    f"'{module.objective}'"
                )

    # exercise_type 必须属于该年龄层允许的类型
    allowed = set(spec.pedagogy.exercise_types)

    for module in spec.modules:
        if module.exercise_type not in allowed:
            problems.append(
                f"{module.module_id}: exercise_type "
                f"'{module.exercise_type}' not allowed for tier "
                f"{spec.pedagogy.tier} "
                f"(allowed: {sorted(allowed)})"
            )

    # 检查概念图中的先后顺序
    if outline_concepts:
        problems += toposort_check(outline_concepts)

    # 除第一个模块外，后续模块都应该有 prerequisite
    for module in spec.modules[1:]:
        if not module.prerequisites:
            problems.append(
                f"{module.module_id}: no prerequisites — "
                "later modules should build on earlier ones"
            )

    return problems


# ---------------------------------------------------------------------------
# Stub planner (deterministic, no API key needed)
# ---------------------------------------------------------------------------

_STUB_SEQUENCE = [
    (
        "What is a program?",
        "what_is_a_program",
    ),
    (
        "Step-by-step instructions",
        "sequences_and_instructions",
    ),
    (
        "Variables: the labelled box",
        "variables",
    ),
    (
        "Talking to the user: input and output",
        "input_output",
    ),
    (
        "Making decisions: conditionals",
        "conditionals",
    ),
    (
        "Doing things again: loops",
        "loops",
    ),
    (
        "Collections: lists",
        "lists",
    ),
    (
        "Reusable steps: functions",
        "functions",
    ),
]


def _stub_plan(
    req: CourseRequest,
    ped,
    n_modules: int,
) -> CourseSpec:
    """Generate a deterministic CourseSpec without calling an LLM."""

    pace = pedagogy.pacing(req.age_bracket)

    # 根据所需模块数量截取固定课程序列
    sequence = _STUB_SEQUENCE[:n_modules]

    modules: list[ModuleSpec] = []

    for index, (title, concept) in enumerate(
        sequence,
        start=1,
    ):
        modules.append(
            ModuleSpec(
                module_id=f"m{index}",
                title=title,
                objective=(
                    f"Understand {concept.replace('_', ' ')}"
                ),
                prerequisites=(
                    [f"m{index - 1}"]
                    if index > 1
                    else []
                ),
                target_minutes=min(
                    pace["default_minutes"],
                    ped.max_session_min,
                ),
                exercise_type=ped.exercise_types[0],
                csta_alignment=ped.key_csta_standards[:1],
            )
        )

    return CourseSpec(
        course_id=(
            f"{req.subject.value.lower().replace(' ', '_')}_"
            f"{req.age_bracket.name.lower()}_"
            f"{uuid.uuid4().hex[:6]}"
        ),
        subject=req.subject,
        age_bracket=req.age_bracket,
        topic=req.topic,
        pedagogy=ped,
        relevancy_note=(
            "[stub] Relevancy check not run — "
            "no LLM was used."
        ),
        references=[
            Reference(
                title=(
                    "CSTA K-12 Computer Science Standards "
                    "(2017)"
                ),
                kind="standard",
                identifier=(
                    "https://csteachers.org/k12standards/"
                ),
            )
        ],
        modules=modules,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def plan_course(
    req: CourseRequest,
    use_llm: bool | None = None,
) -> CourseSpec:
    """Turn a CourseRequest into a validated CourseSpec.

    Args:
        req:
            Structured course request.

        use_llm:
            None:
                Automatically use OpenRouter when OPENROUTER_API_KEY exists.
                Otherwise use the local stub planner.

            False:
                Always use the local stub planner.

            True:
                Always use OpenRouter. A RuntimeError is raised if the
                API key is unavailable.

    Returns:
        A validated CourseSpec.
    """

    # -----------------------------------------------------------------------
    # Stage 0 — age-tier pedagogy lookup
    # -----------------------------------------------------------------------

    # 根据年龄获取教学规则
    ped = pedagogy.lookup(req.age_bracket)

    # 获取该年龄段的课程节奏设置
    pace = pedagogy.pacing(req.age_bracket)

    # 用户指定模块数量时使用用户设置；
    # 否则使用该年龄段的默认模块数量
    n_modules = (
        req.max_modules
        or pace["default_modules"]
    )

    # use_llm=None 表示自动检测
    if use_llm is None:
        use_llm = bool(
            os.environ.get("OPENROUTER_API_KEY")
        )

    # 不使用 LLM 时直接返回本地 stub
    if not use_llm:
        return _stub_plan(
            req,
            ped,
            n_modules,
        )

    # -----------------------------------------------------------------------
    # Stage 1 — high-level outline
    # -----------------------------------------------------------------------

    stage1_prompt = _stage1_prompt(
        req,
        ped,
        n_modules,
    )

    outline_text = _call_llm(stage1_prompt)
    outline = _parse_json(outline_text)

    # Stage 1 必须返回 JSON 数组
    if not isinstance(outline, list):
        raise ValueError(
            "Stage 1 must return a JSON array of modules."
        )

    # 防止模型返回错误模块数量
    if len(outline) != n_modules:
        raise ValueError(
            f"Stage 1 returned {len(outline)} modules, "
            f"but exactly {n_modules} were requested."
        )

    # 提取概念，供 Stage 3 检查概念图顺序
    concepts = [
        module.get("concept", "")
        for module in outline
        if isinstance(module, dict)
    ]

    # -----------------------------------------------------------------------
    # Stage 2 — full course expansion
    # -----------------------------------------------------------------------

    stage2_prompt = _stage2_prompt(
        req,
        ped,
        outline,
    )

    expanded_text = _call_llm(stage2_prompt)
    expanded = _parse_json(expanded_text)

    # Stage 2 必须返回 JSON 对象
    if not isinstance(expanded, dict):
        raise ValueError(
            "Stage 2 must return a JSON object."
        )

    if "modules" not in expanded:
        raise ValueError(
            "Stage 2 response is missing the 'modules' field."
        )

    # Pydantic 模型会继续检查字段类型和数据约束
    spec = CourseSpec(
        course_id=(
            f"{req.subject.value.lower().replace(' ', '_')}_"
            f"{req.age_bracket.name.lower()}_"
            f"{uuid.uuid4().hex[:6]}"
        ),
        subject=req.subject,
        age_bracket=req.age_bracket,
        topic=req.topic,
        pedagogy=ped,
        relevancy_note=expanded.get(
            "relevancy_note",
            "",
        ),
        references=[
            Reference(**reference)
            for reference in expanded.get(
                "references",
                [],
            )
        ],
        modules=[
            ModuleSpec(**module)
            for module in expanded["modules"]
        ],
    )

    # -----------------------------------------------------------------------
    # Stage 3 — rule check with one repair round
    # -----------------------------------------------------------------------

    problems = rule_check(
        spec,
        concepts,
    )

    if problems:
        repair_prompt = (
            stage2_prompt
            + "\n\n"
            + "Your previous answer had these violations. "
            + "Fix ALL of them and respond with the corrected "
            + "JSON object only:\n- "
            + "\n- ".join(problems)
        )

        repaired_text = _call_llm(repair_prompt)
        repaired = _parse_json(repaired_text)

        if not isinstance(repaired, dict):
            raise ValueError(
                "The repair response must be a JSON object."
            )

        if "modules" not in repaired:
            raise ValueError(
                "The repair response is missing the "
                "'modules' field."
            )

        repaired_references = [
            Reference(**reference)
            for reference in repaired.get(
                "references",
                [],
            )
        ]

        spec = spec.model_copy(
            update={
                "relevancy_note": repaired.get(
                    "relevancy_note",
                    spec.relevancy_note,
                ),
                "references": (
                    repaired_references
                    or spec.references
                ),
                "modules": [
                    ModuleSpec(**module)
                    for module in repaired["modules"]
                ],
            }
        )

        # 修复后重新检查
        remaining = rule_check(
            spec,
            concepts,
        )

        if remaining:
            raise ValueError(
                "Course spec failed rule validation "
                "after the repair round:\n- "
                + "\n- ".join(remaining)
            )

    return spec