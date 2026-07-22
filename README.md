# Agent A — Curriculum Architect (LectMate / Project A1)

Owner: **Yisong** · v0.1 · Pilot scope: Coding × all four age brackets (stub) / Creators 10–13 (LLM)

Turns a course request (`subject + age bracket + topic + objectives`) into a validated **Course Spec** for Agent B, with pedagogy constraints, CSTA grounding references, and a topic-relevancy note baked in.

## How it works

```
CourseRequest
   │
   ├─ Stage 0  Age-tier lookup (T03 Content Design Matrix → pedagogy.py)
   │           gates ALL downstream constraints
   ├─ Stage 1  LLM proposes high-level module outline (titles + concepts)
   ├─ Stage 2  LLM expands: objectives, prerequisites, minutes, exercise types,
   │           CSTA alignment, relevancy note, grounding references
   └─ Stage 3  Rule validation (Pydantic schema + concept graph + tier caps);
               one automatic repair round on failure
   ▼
CourseSpec (JSON, schema v0.5.0)
```

Design decisions traceable to project docs:

| Feature | Source |
|---|---|
| Two-stage hierarchical planning | Game Plan §5 "Techniques worth trying" |
| Pedagogy matrix as hard constraints | T03 Content Design Matrix (Sprint 1 research) |
| Prerequisite concept graph check | Game Plan §5; CSTA 2017 progression |
| `references` + `relevancy_note` fields | 2 Jul meeting (grounding/anchors, relevancy check) |
| Stub mode for B/C integration | Game Plan §9 "build against a stub" |
| Agent-level unit tests before handoff | 2 Jul meeting (test at every level) |

## Run it

```bash
pip install -r requirements.txt

# Stub mode (no API key, deterministic — for B/C to integrate against)
python -m agent_a.cli --subject Coding --age "Creators (10-13)" \
    --topic "Python fundamentals" --stub

# LLM mode (real planning)
export OPENROUTER_API_KEY=sk-or-...
python -m agent_a.cli --subject Coding --age "Creators (10-13)" \
    --topic "Python fundamentals" --out spec.json

# Fixed pedagogy mode (default): use the local age-tier pedagogy matrix
python -m agent_a.cli --subject Coding --age "Creators (10-13)" \
    --topic "Python fundamentals" --mode fixed --out spec.json --html review.html

# ADDIE discovery mode: use Analyze/Design reasoning for a new course
python -m agent_a.cli --subject AI --age "Innovators (14-17)" \
    --topic "Data visualisation with Python" --mode addie \
    --requirement "Prefer project-based learning" \
    --requirement "Include portfolio-ready outputs" \
    --out spec.json --html review.html

# Human review page (prints a file:// link for curriculum designers)
python -m agent_a.cli --subject Coding --age "Creators (10-13)" \
    --topic "Python fundamentals" --stub --out spec.json --html review.html

# Intake chatbot: clarify designer needs before generation
python -m agent_a.intake_cli --stub \
    --message "我想做一门 AI 课程，主题是 Data visualisation with Python，面向 14-17 岁学生，使用 addie 模式，最好项目制，8 个模块。" \
    --out course_request.json

# Generate from the confirmed intake request
python -m agent_a.cli --request course_request.json \
    --stub --out spec.json --html review.html

# Revision flow: old JSON + change request -> new JSON/HTML/report
python -m agent_a.revise --in spec.json \
    --change "把课程改成 8 个模块，并加强项目制学习" \
    --out spec_v2.json --html review_v2.html \
    --report revision_report.md

# Tests
python -m pytest tests/ -q
```

`--out` keeps the machine-readable CourseSpec JSON for Agent B/C handoff.
`--html` writes a self-contained review page using the three-level product
information pattern:

- Level A: landing page card with course name, level, age group, lesson range,
  one-sentence description, and skill tags
- Level B: pre-login overview with tagline, learning bullets, build outcome,
  and course rationale
- Level C: post-login full course page with phases, modules, learning outcomes,
  tools, prerequisites, and progress tracking

The LLM path now produces `overview` and `phases` fields in addition to the
machine-readable module list, references, pedagogy constraints, and relevancy
note. Stub mode generates deterministic display data for local demos.

`--mode fixed` keeps the original flow: the local pedagogy matrix is the hard
design frame. `--mode addie` adds an `addie` block with Analyze and Design phase
reasoning, inspired by the Instructional Agents ADDIE workflow, while still
keeping age-appropriate safety constraints and the same CourseSpec handoff.
Use repeatable `--requirement` flags to pass curriculum-designer preferences.

The schema also derives a `packaging` block from the module list. This captures
the automation contract from `Course_Component_Structure.docx`: Course Slides,
Exercise Bank, Quiz Bank, Assignment Bank, and Additional resources; per-module
folder names; split file names; 6 exercises, 10 quiz questions, and 3
assignments per module; cross-bank relationships; and validation checks.

Python usage:

```python
from agent_a import CourseRequest, Subject, AgeBracket, plan_course
req = CourseRequest(subject=Subject.CODING, age_bracket=AgeBracket.CREATORS,
                    topic="Python fundamentals")
spec = plan_course(req)          # auto: LLM if key present, stub otherwise
print(spec.model_dump_json(indent=2))
```

## Revision workflow

The generated `spec.json` and `review.html` are static outputs, but the project
now includes a revision loop for controlled edits:

1. Load the old `spec.json`
2. Read one or more `--change` requests
3. Ask the LLM to produce a complete revised CourseSpec JSON
4. Run programmatic validation: schema, prerequisites, pedagogy rules, phase
   coverage, packaging, and HTML rendering
5. Compare old vs new modules, phases, and packaging totals
6. Ask the LLM reviewer whether the new spec satisfies the requested change
7. Write `spec_v2.json`, `review_v2.html`, and `revision_report.md`

Use `--stub` for deterministic local testing without an API key. With
`OPENROUTER_API_KEY` set, revision and reviewer both use the LLM unless
`--no-llm-reviewer` is passed.

Once downstream resource banks have been generated, keep module titles stable
where possible because `Module N - <Title>` is the join key across slides,
exercises, quizzes, assignments, and packaging metadata.

## Intake chatbot workflow

The intake chatbot is the front door for curriculum designers. It does not
generate the course directly. It turns a conversation into a confirmed
`CourseRequest`:

1. Gather subject, age bracket, topic, planning mode, objectives, requirements,
   and optional module count
2. Ask follow-up questions when required fields are missing
3. Write `course_request.json` once the request is ready
4. Pass that request into `agent_a.cli` for fixed/addie generation

Use `--stub` for deterministic local extraction. With `OPENROUTER_API_KEY` set,
the intake chatbot can use the LLM to summarize messier conversations.

## Schema changes vs Game Plan §4.1 (⚠ needs team sign-off)

Added fields — raise with B & C owners and log in the shared changelog:

- `pedagogy` (object) — tier constraints Agent B must inject into its prompts
- `relevancy_note` (str) — topic-currency check result
- `references` (list) — grounding sources for Agent C to verify against
- per-module: `title`, `exercise_type`, `csta_alignment`
- `overview` and `phases` — Level A/B/C page data for product display
- `packaging` — resource-bank, split-file, and validation metadata derived from
  the module list
- `addie` — Analyze and Design phase record for new-course discovery and
  curriculum-designer review
- `schema_version` — for changelog tracking

## Known gaps / next steps

- [ ] Relevancy check currently relies on the LLM's own judgment; wire in web
      search or the company's trend-agent as an input source (`CourseRequest.source`)
- [ ] Concept graphs exist only for Coding/Python; add AI, Financial Literacy,
      Entrepreneurship
- [ ] Tier boundaries are hard-coded; add curriculum-engineer override
      (open question from the pedagogy doc §5.4)
- [ ] Evaluation rubric for pedagogical coherence (dissertation performance
      measure) — needs formal metric definition
- [ ] Align spec fields with the Next Script sample course / tutor master
      document once the curriculum engineer shares it (next meeting)
