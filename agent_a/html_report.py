"""Human-readable HTML review report for CourseSpec objects."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

from .schemas import CourseSpec


def _items(values: list[str]) -> str:
    if not values:
        return '<span class="muted">None</span>'
    return "".join(f"<li>{escape(value)}</li>" for value in values)


def _chips(values: list[str]) -> str:
    if not values:
        return '<span class="muted">None</span>'
    return "".join(f'<span class="chip">{escape(value)}</span>' for value in values)


def _module_rows(spec: CourseSpec) -> str:
    rows: list[str] = []
    for module in spec.modules:
        prerequisites = (
            ", ".join(module.prerequisites)
            if module.prerequisites
            else "None"
        )
        rows.append(
            f"""
            <article class="module">
              <div class="module-head">
                <span class="module-id">{escape(module.module_id)}</span>
                <h3>{escape(module.title)}</h3>
              </div>
              <p class="objective">{escape(module.objective)}</p>
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
    return "\n".join(rows)


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


def render_course_spec_html(spec: CourseSpec) -> str:
    """Render a CourseSpec as a self-contained HTML page."""

    raw_json = spec.model_dump_json(indent=2)
    ped = spec.pedagogy

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(spec.topic)} - Course Review</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #1c2430;
      --muted: #647084;
      --line: #d9e0ea;
      --paper: #ffffff;
      --surface: #f5f7fb;
      --accent: #0f766e;
      --accent-soft: #dff4f0;
      --warn: #a16207;
      --warn-soft: #fff4cc;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--surface);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
      line-height: 1.5;
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding-bottom: 22px;
      margin-bottom: 24px;
    }}
    .eyebrow {{
      color: var(--accent);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }}
    h1 {{
      font-size: 34px;
      line-height: 1.15;
      margin: 8px 0 10px;
    }}
    h2 {{
      font-size: 20px;
      margin: 0 0 14px;
    }}
    h3 {{
      font-size: 17px;
      margin: 0;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .stat, section, .module {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .stat {{
      padding: 12px 14px;
    }}
    .label, dt {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
    }}
    .value, dd {{
      margin: 4px 0 0;
      font-weight: 650;
    }}
    section {{
      padding: 20px;
      margin: 16px 0;
    }}
    .pedagogy-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px 18px;
    }}
    .module-list {{
      display: grid;
      gap: 12px;
    }}
    .module {{
      padding: 16px;
    }}
    .module-head {{
      display: flex;
      gap: 10px;
      align-items: center;
      margin-bottom: 8px;
    }}
    .module-id {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 36px;
      height: 28px;
      border-radius: 6px;
      background: var(--accent-soft);
      color: var(--accent);
      font-weight: 800;
      font-size: 13px;
      flex: 0 0 auto;
    }}
    .objective {{
      margin: 0 0 14px;
    }}
    .module-meta {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin: 0 0 12px;
    }}
    .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .chip {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 9px;
      background: #fafcff;
      font-size: 13px;
    }}
    .note {{
      border-left: 4px solid var(--warn);
      background: var(--warn-soft);
      padding: 12px 14px;
      border-radius: 6px;
      margin: 0;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid var(--line);
      padding: 10px 8px;
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
      margin-top: 16px;
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
    ul {{
      margin: 6px 0 0;
      padding-left: 18px;
    }}
    @media (max-width: 760px) {{
      main {{ padding: 22px 14px 36px; }}
      h1 {{ font-size: 28px; }}
      .summary, .pedagogy-grid, .module-meta {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div class="eyebrow">LectMate Agent A Course Review</div>
      <h1>{escape(spec.topic)}</h1>
      <p class="muted">
        {escape(spec.subject.value)} for {escape(spec.age_bracket.value)}
      </p>
      <div class="summary">
        <div class="stat">
          <div class="label">Course ID</div>
          <div class="value">{escape(spec.course_id)}</div>
        </div>
        <div class="stat">
          <div class="label">Modules</div>
          <div class="value">{len(spec.modules)}</div>
        </div>
        <div class="stat">
          <div class="label">Tier</div>
          <div class="value">T{ped.tier}</div>
        </div>
        <div class="stat">
          <div class="label">Schema</div>
          <div class="value">{escape(spec.schema_version)}</div>
        </div>
      </div>
    </header>

    <section>
      <h2>Course Modules</h2>
      <div class="module-list">
        {_module_rows(spec)}
      </div>
    </section>

    <section>
      <h2>Pedagogy Constraints</h2>
      <div class="pedagogy-grid">
        <div>
          <div class="label">Cognitive Theory</div>
          <div class="value">{escape(ped.cognitive_theory)}</div>
        </div>
        <div>
          <div class="label">CSTA Level</div>
          <div class="value">{escape(ped.csta_level)}</div>
        </div>
        <div>
          <div class="label">Raw Text Code</div>
          <div class="value">{escape(ped.raw_text_code_allowed)}</div>
        </div>
        <div>
          <div class="label">Content Format</div>
          <div class="value">{escape(ped.content_format)}</div>
        </div>
        <div>
          <div class="label">Metaphor / Story</div>
          <div class="value">{escape(ped.metaphor_story)}</div>
        </div>
        <div>
          <div class="label">Max Session</div>
          <div class="value">{ped.max_session_min} min</div>
        </div>
        <div>
          <div class="label">Tester Mode</div>
          <div class="value">{escape(ped.tester_mode)}</div>
        </div>
        <div>
          <div class="label">Tutor Guide</div>
          <div class="value">{escape(ped.tutor_guide_style)}</div>
        </div>
        <div>
          <div class="label">Feedback Style</div>
          <div class="value">{escape(ped.feedback_style)}</div>
        </div>
        <div>
          <div class="label">Mini Project</div>
          <div class="value">{escape(ped.mini_project_type)}</div>
        </div>
        <div>
          <div class="label">Exercise Types</div>
          <ul>{_items(ped.exercise_types)}</ul>
        </div>
        <div>
          <div class="label">Key CSTA Standards</div>
          <ul>{_items(ped.key_csta_standards)}</ul>
        </div>
      </div>
    </section>

    <section>
      <h2>Relevancy Note</h2>
      <p class="note">{escape(spec.relevancy_note or "No relevancy note provided.")}</p>
    </section>

    <section>
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
