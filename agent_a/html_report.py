"""Human-readable Level A/B/C HTML pages for CourseSpec objects."""
from __future__ import annotations

from html import escape
from pathlib import Path

from .schemas import CoursePhase, CourseSpec


def _items(values: list[str]) -> str:
    if not values:
        return '<li class="muted">None</li>'
    return "".join(f"<li>{escape(value)}</li>" for value in values)


def _chips(values: list[str]) -> str:
    if not values:
        return '<span class="muted">None</span>'
    return "".join(f'<span class="chip">{escape(value)}</span>' for value in values)


def _age_group(spec: CourseSpec) -> str:
    value = spec.age_bracket.value
    if "(" in value and ")" in value:
        return value.split("(", 1)[1].split(")", 1)[0]
    return value


def _level(spec: CourseSpec) -> str:
    return spec.overview.level or f"Tier {spec.pedagogy.tier}"


def _lesson_range(spec: CourseSpec) -> str:
    if spec.overview.lesson_range:
        return spec.overview.lesson_range
    return f"{len(spec.modules)} modules"


def _duration(spec: CourseSpec) -> str:
    if spec.overview.duration:
        return spec.overview.duration
    return "Tutor-paced"


def _description(spec: CourseSpec) -> str:
    if spec.overview.one_sentence_description:
        return spec.overview.one_sentence_description
    return f"Learn {spec.topic} through a structured, age-appropriate course journey."


def _skill_tags(spec: CourseSpec) -> list[str]:
    if spec.overview.skill_tags:
        return spec.overview.skill_tags
    return [spec.subject.value, spec.topic]


def _module_lookup(spec: CourseSpec):
    return {module.module_id: module for module in spec.modules}


def _fallback_phases(spec: CourseSpec) -> list[CoursePhase]:
    if spec.phases:
        return spec.phases

    module_count = len(spec.modules)
    phase_count = min(3, module_count)
    phase_titles = ["Foundations", "Core Skills", "Applied Practice"]
    phases: list[CoursePhase] = []
    for index in range(phase_count):
        start = (index * module_count) // phase_count + 1
        end = ((index + 1) * module_count) // phase_count
        phases.append(
            CoursePhase(
                phase_id=f"p{index + 1}",
                title=phase_titles[index],
                module_ids=[
                    f"m{module_index}"
                    for module_index in range(start, end + 1)
                ],
            )
        )
    return phases


def _phase_sections(spec: CourseSpec) -> str:
    modules = _module_lookup(spec)
    sections: list[str] = []
    for phase in _fallback_phases(spec):
        module_rows: list[str] = []
        for module_id in phase.module_ids:
            module = modules[module_id]
            prerequisites = (
                ", ".join(module.prerequisites)
                if module.prerequisites
                else "None"
            )
            module_rows.append(
                f"""
                <article class="module">
                  <div class="module-head">
                    <span class="module-id">{escape(module.module_id)}</span>
                    <h4>{escape(module.title)}</h4>
                  </div>
                  <p>{escape(module.objective)}</p>
                  <dl class="module-meta">
                    <div>
                      <dt>Minutes</dt>
                      <dd>{module.target_minutes}</dd>
                    </div>
                    <div>
                      <dt>Exercise</dt>
                      <dd>{escape(module.exercise_type)}</dd>
                    </div>
                    <div>
                      <dt>Prerequisites</dt>
                      <dd>{escape(prerequisites)}</dd>
                    </div>
                  </dl>
                  <div class="chips">{_chips(module.csta_alignment)}</div>
                </article>
                """
            )
        sections.append(
            f"""
            <section class="phase">
              <div class="phase-head">
                <span>{escape(phase.phase_id.upper())}</span>
                <h3>{escape(phase.title)}</h3>
              </div>
              <div class="module-list">
                {"".join(module_rows)}
              </div>
            </section>
            """
        )
    return "".join(sections)


def _reference_rows(spec: CourseSpec) -> str:
    if not spec.references:
        return '<p class="muted">No references provided.</p>'

    rows = []
    for reference in spec.references:
        rows.append(
            f"""
            <tr>
              <td>{escape(reference.title)}</td>
              <td>{escape(reference.kind)}</td>
              <td>{escape(reference.identifier)}</td>
            </tr>
            """
        )
    return (
        """
        <table>
          <thead>
            <tr><th>Title</th><th>Kind</th><th>Identifier</th></tr>
          </thead>
          <tbody>
        """
        + "\n".join(rows)
        + """
          </tbody>
        </table>
        """
    )


def _component_bank_rows(spec: CourseSpec) -> str:
    rows = []
    for bank in spec.packaging.component_banks:
        units = (
            str(bank.units_per_module)
            if bank.units_per_module is not None
            else "varies"
        )
        total = (
            str(bank.total_units)
            if bank.total_units is not None
            else "varies"
        )
        rows.append(
            f"""
            <tr>
              <td>{escape(bank.folder_name)}</td>
              <td>{escape(bank.master_file)}</td>
              <td>{escape(bank.per_module_unit)}</td>
              <td>{escape(units)}</td>
              <td>{escape(total)}</td>
              <td>{escape(bank.split_file_name)}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _module_package_rows(spec: CourseSpec) -> str:
    rows = []
    for package in spec.packaging.module_packages:
        rows.append(
            f"""
            <tr>
              <td>{package.module_index}</td>
              <td>{escape(package.module_title)}</td>
              <td>{escape(package.folder_name)}</td>
              <td>{escape(package.slides_file)}</td>
              <td>{escape(package.exercises_file)}</td>
              <td>{escape(package.questions_file)}</td>
              <td>{escape(package.assignments_file)}</td>
            </tr>
            """
        )
    return "\n".join(rows)


def _addie_section(spec: CourseSpec) -> str:
    analysis = spec.addie.analysis
    design = spec.addie.design
    return f"""
    <section class="page">
      <h2>ADDIE Analysis & Design</h2>
      <div class="section-grid">
        <div class="mini-card">
          <h3>Analyze Phase</h3>
          <dl>
            <div>
              <dt>Target Audience</dt>
              <dd>{escape(analysis.target_audience or "Not specified")}</dd>
            </div>
            <div>
              <dt>Learner Context</dt>
              <dd>{escape(analysis.learner_context or "Not specified")}</dd>
            </div>
          </dl>
          <h4>Prior Knowledge</h4>
          <ul>{_items(analysis.prior_knowledge_assumptions)}</ul>
          <h4>Learner Needs</h4>
          <ul>{_items(analysis.learner_needs)}</ul>
          <h4>Resources & Constraints</h4>
          <ul>{_items(analysis.resource_constraints)}</ul>
        </div>
        <div class="mini-card">
          <h3>Design Phase</h3>
          <dl>
            <div>
              <dt>Instructional Strategy</dt>
              <dd>{escape(design.instructional_strategy or "Not specified")}</dd>
            </div>
            <div>
              <dt>Sequence Rationale</dt>
              <dd>{escape(design.module_sequence_rationale or "Not specified")}</dd>
            </div>
            <div>
              <dt>Assessment Strategy</dt>
              <dd>{escape(design.assessment_strategy or "Not specified")}</dd>
            </div>
            <div>
              <dt>Engagement Strategy</dt>
              <dd>{escape(design.engagement_strategy or "Not specified")}</dd>
            </div>
            <div>
              <dt>Differentiation</dt>
              <dd>{escape(design.differentiation_strategy or "Not specified")}</dd>
            </div>
          </dl>
          <h4>Success Criteria</h4>
          <ul>{_items(design.success_criteria)}</ul>
        </div>
        <div class="mini-card">
          <h3>Designer Requirements</h3>
          <ul>{_items(analysis.designer_requirements)}</ul>
        </div>
        <div class="mini-card">
          <h3>Open Questions & Revision Notes</h3>
          <h4>Open Questions</h4>
          <ul>{_items(analysis.open_questions)}</ul>
          <h4>Revision Notes</h4>
          <ul>{_items(design.revision_notes)}</ul>
        </div>
      </div>
    </section>
    """


def render_course_spec_html(spec: CourseSpec) -> str:
    """Render Level A, B, and C course pages in one self-contained HTML file."""

    raw_json = spec.model_dump_json(indent=2)
    overview = spec.overview
    ped = spec.pedagogy

    learn_items = overview.what_you_will_learn or [
        module.objective
        for module in spec.modules[:6]
    ]
    outcomes = overview.learning_outcomes or [
        module.objective
        for module in spec.modules
    ]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(spec.topic)} - Course Pages</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #667085;
      --line: #d7dde6;
      --paper: #ffffff;
      --surface: #f4f6f8;
      --accent: #0f766e;
      --accent-soft: #dff4f0;
      --blue: #1d4ed8;
      --blue-soft: #e7efff;
      --gold: #9a6500;
      --gold-soft: #fff4d7;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--surface);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system,
        BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    .topbar {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
      padding-bottom: 20px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 18px;
    }}
    .eyebrow {{
      color: var(--accent);
      font-size: 13px;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{
      font-size: 36px;
      line-height: 1.12;
      margin: 8px 0 8px;
    }}
    h2 {{
      font-size: 22px;
      margin: 0 0 14px;
    }}
    h3 {{
      font-size: 18px;
      margin: 0;
    }}
    h4 {{
      font-size: 16px;
      margin: 0;
    }}
    .page {{
      margin: 18px 0;
      padding: 22px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
    }}
    .page-label {{
      display: inline-flex;
      align-items: center;
      padding: 5px 9px;
      border-radius: 6px;
      background: var(--blue-soft);
      color: var(--blue);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .landing-card {{
      max-width: 640px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      background: #fbfcfe;
    }}
    .info-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 16px 0;
    }}
    .info, .mini-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfe;
    }}
    .label, dt {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .value, dd {{
      margin: 4px 0 0;
      font-weight: 650;
    }}
    .tagline {{
      font-size: 21px;
      max-width: 780px;
      margin: 10px 0 16px;
      font-weight: 680;
    }}
    .section-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
    }}
    .full-width {{
      grid-column: 1 / -1;
    }}
    ul, ol {{
      margin: 8px 0 0;
      padding-left: 22px;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }}
    .chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 9px;
      background: #ffffff;
      font-size: 13px;
    }}
    .phase {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #fbfcfe;
      margin: 12px 0;
    }}
    .phase-head {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .phase-head span, .module-id {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 6px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 800;
      flex: 0 0 auto;
    }}
    .phase-head span {{
      min-width: 38px;
      height: 28px;
      font-size: 12px;
    }}
    .module-list {{
      display: grid;
      gap: 10px;
    }}
    .module {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
      padding: 14px;
    }}
    .module-head {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 6px;
    }}
    .module-id {{
      width: 36px;
      height: 28px;
      font-size: 13px;
    }}
    .module p {{
      margin: 0 0 12px;
    }}
    .module-meta {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin: 0 0 10px;
    }}
    .note {{
      border-left: 4px solid var(--gold);
      background: var(--gold-soft);
      border-radius: 6px;
      padding: 12px 14px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 8px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
    }}
    details {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px 20px;
      margin-top: 18px;
    }}
    summary {{
      cursor: pointer;
      font-weight: 750;
    }}
    pre {{
      overflow: auto;
      background: #111827;
      color: #e5e7eb;
      border-radius: 8px;
      padding: 16px;
      font-size: 13px;
    }}
    .muted {{
      color: var(--muted);
    }}
    @media (max-width: 820px) {{
      main {{ padding: 20px 14px 36px; }}
      h1 {{ font-size: 29px; }}
      .topbar, .section-grid {{
        display: block;
      }}
      .info-grid, .module-meta {{
        grid-template-columns: 1fr;
      }}
      .mini-card {{
        margin-bottom: 12px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <div class="topbar">
      <div>
        <div class="eyebrow">LectMate Agent A Course Pages</div>
        <h1>{escape(spec.topic)}</h1>
        <p class="muted">
          Stream: {escape(spec.subject.value)} · Ages {escape(_age_group(spec))} · {escape(_level(spec))}
        </p>
      </div>
      <div class="info">
        <div class="label">Planning Mode</div>
        <div class="value">{escape(spec.planning_mode.value)}</div>
      </div>
      <div class="info">
        <div class="label">Schema</div>
        <div class="value">{escape(spec.schema_version)}</div>
      </div>
    </div>

    <section class="page" id="level-a">
      <span class="page-label">Level A - Landing Page Card</span>
      <h2>Landing Card</h2>
      <div class="landing-card">
        <h3>{escape(spec.topic)}</h3>
        <div class="info-grid">
          <div>
            <div class="label">Level</div>
            <div class="value">{escape(_level(spec))}</div>
          </div>
          <div>
            <div class="label">Age Group</div>
            <div class="value">{escape(_age_group(spec))}</div>
          </div>
          <div>
            <div class="label">Lesson Range</div>
            <div class="value">{escape(_lesson_range(spec))}</div>
          </div>
          <div>
            <div class="label">Modules</div>
            <div class="value">{len(spec.modules)}</div>
          </div>
        </div>
        <p>{escape(_description(spec))}</p>
        <div class="chips">{_chips(_skill_tags(spec))}</div>
      </div>
    </section>

    <section class="page" id="level-b">
      <span class="page-label">Level B - Course Overview Page (Pre-Login)</span>
      <h2>Course Overview</h2>
      <p class="tagline">
        {escape(overview.tagline or _description(spec))}
      </p>
      <div class="info-grid">
        <div class="info">
          <div class="label">Course Title</div>
          <div class="value">{escape(spec.topic)}</div>
        </div>
        <div class="info">
          <div class="label">Level</div>
          <div class="value">{escape(_level(spec))}</div>
        </div>
        <div class="info">
          <div class="label">Age Group</div>
          <div class="value">{escape(_age_group(spec))}</div>
        </div>
        <div class="info">
          <div class="label">Duration</div>
          <div class="value">{escape(_duration(spec))}</div>
        </div>
      </div>
      <div class="section-grid">
        <div class="mini-card">
          <h3>What You Will Learn</h3>
          <ul>{_items(learn_items)}</ul>
        </div>
        <div class="mini-card">
          <h3>What You Will Build</h3>
          <p>{escape(overview.what_you_will_build or "A final project that demonstrates the course concepts.")}</p>
        </div>
        <div class="mini-card full-width">
          <h3>Why This Course</h3>
          <p>{escape(overview.why_this_course or spec.relevancy_note or "This course builds useful foundations through structured practice.")}</p>
        </div>
      </div>
    </section>

    <section class="page" id="level-c">
      <span class="page-label">Level C - Full Course Page (Post-Login)</span>
      <h2>Full Course Journey</h2>
      {_phase_sections(spec)}

      <div class="section-grid">
        <div class="mini-card">
          <h3>Learning Outcomes</h3>
          <ol>{_items(outcomes)}</ol>
        </div>
        <div class="mini-card">
          <h3>Tools You Will Use</h3>
          <ul>{_items(overview.tools_you_will_use)}</ul>
        </div>
        <div class="mini-card">
          <h3>Prerequisites & Entry Requirements</h3>
          <ul>{_items(overview.prerequisites)}</ul>
        </div>
        <div class="mini-card">
          <h3>Progress & Module Tracking</h3>
          <ul>{_items(overview.progress_tracking)}</ul>
        </div>
      </div>
    </section>

    {_addie_section(spec)}

    <section class="page">
      <h2>Automation Packaging</h2>
      <p class="muted">
        Module index and module title are the join key across the specification,
        slides, exercises, quizzes, assignments, and shared resources.
      </p>
      <div class="section-grid">
        <div class="mini-card">
          <h3>Resource Banks</h3>
          <ul>{_items(spec.packaging.bank_folders)}</ul>
        </div>
        <div class="mini-card">
          <h3>Fixed Counts</h3>
          <ul>
            <li>{spec.packaging.exercises_per_module} exercises per module</li>
            <li>{spec.packaging.quiz_questions_per_module} quiz questions per module</li>
            <li>{spec.packaging.assignments_per_module} assignments per module</li>
          </ul>
        </div>
      </div>
      <h3>Component Structure</h3>
      <table>
        <thead>
          <tr>
            <th>Component</th>
            <th>Master</th>
            <th>Per-module unit</th>
            <th>Units/module</th>
            <th>Total</th>
            <th>Split file</th>
          </tr>
        </thead>
        <tbody>
          {_component_bank_rows(spec)}
        </tbody>
      </table>
      <h3>Module Package Map</h3>
      <table>
        <thead>
          <tr>
            <th>N</th>
            <th>Module title</th>
            <th>Folder</th>
            <th>Slides</th>
            <th>Exercises</th>
            <th>Questions</th>
            <th>Assignments</th>
          </tr>
        </thead>
        <tbody>
          {_module_package_rows(spec)}
        </tbody>
      </table>
      <div class="section-grid">
        <div class="mini-card">
          <h3>Relationships</h3>
          <ul>{_items(spec.packaging.relationships)}</ul>
        </div>
        <div class="mini-card">
          <h3>Validation Checklist</h3>
          <ul>{_items(spec.packaging.validation_checklist)}</ul>
        </div>
      </div>
    </section>

    <section class="page">
      <h2>Pedagogy Constraints</h2>
      <div class="section-grid">
        <div class="mini-card">
          <div class="label">Cognitive Theory</div>
          <div class="value">{escape(ped.cognitive_theory)}</div>
        </div>
        <div class="mini-card">
          <div class="label">CSTA Level</div>
          <div class="value">{escape(ped.csta_level)}</div>
        </div>
        <div class="mini-card">
          <div class="label">Content Format</div>
          <div class="value">{escape(ped.content_format)}</div>
        </div>
        <div class="mini-card">
          <div class="label">Mini Project</div>
          <div class="value">{escape(ped.mini_project_type)}</div>
        </div>
      </div>
    </section>

    <section class="page">
      <h2>Relevancy Note</h2>
      <p class="note">{escape(spec.relevancy_note or "No relevancy note provided.")}</p>
    </section>

    <section class="page">
      <h2>References</h2>
      {_reference_rows(spec)}
    </section>

    <details>
      <summary>Raw CourseSpec JSON</summary>
      <pre><code>{escape(raw_json)}</code></pre>
    </details>
  </main>
</body>
</html>
"""


def write_course_spec_html(
    spec: CourseSpec,
    path: str | Path,
) -> Path:
    """Write a CourseSpec review page and return the resolved file path."""

    output_path = Path(path).expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_course_spec_html(spec),
        encoding="utf-8",
    )
    return output_path.resolve()
