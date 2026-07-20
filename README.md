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
CourseSpec (JSON, schema v0.3.0)
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
export ANTHROPIC_API_KEY=sk-...
python -m agent_a.cli --subject Coding --age "Creators (10-13)" \
    --topic "Python fundamentals" --out spec.json

# Human review page (prints a file:// link for curriculum designers)
python -m agent_a.cli --subject Coding --age "Creators (10-13)" \
    --topic "Python fundamentals" --stub --out spec.json --html review.html

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

Python usage:

```python
from agent_a import CourseRequest, Subject, AgeBracket, plan_course
req = CourseRequest(subject=Subject.CODING, age_bracket=AgeBracket.CREATORS,
                    topic="Python fundamentals")
spec = plan_course(req)          # auto: LLM if key present, stub otherwise
print(spec.model_dump_json(indent=2))
```

## Schema changes vs Game Plan §4.1 (⚠ needs team sign-off)

Added fields — raise with B & C owners and log in the shared changelog:

- `pedagogy` (object) — tier constraints Agent B must inject into its prompts
- `relevancy_note` (str) — topic-currency check result
- `references` (list) — grounding sources for Agent C to verify against
- per-module: `title`, `exercise_type`, `csta_alignment`
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
