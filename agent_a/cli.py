"""CLI: python -m agent_a.cli --subject Coding --age "Creators (10-13)" --topic "Python fundamentals" """
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .html_report import write_course_spec_html
from .planner import plan_course
from .schemas import AgeBracket, CourseRequest, PlanningMode, Subject


def main() -> int:
    p = argparse.ArgumentParser(description="Agent A — Curriculum Architect")
    p.add_argument("--request", default=None, help="read CourseRequest JSON from intake")
    p.add_argument("--subject", choices=[s.value for s in Subject])
    p.add_argument("--age", choices=[a.value for a in AgeBracket])
    p.add_argument("--topic")
    p.add_argument("--objective", action="append", default=[], help="repeatable")
    p.add_argument(
        "--requirement",
        action="append",
        default=[],
        help="repeatable course designer requirement or constraint",
    )
    p.add_argument("--modules", type=int, default=None)
    p.add_argument(
        "--mode",
        default=PlanningMode.FIXED_PEDAGOGY.value,
        choices=[mode.value for mode in PlanningMode],
        help="'fixed' uses the pedagogy matrix; 'addie' adds Analyze/Design discovery",
    )
    p.add_argument("--stub", action="store_true", help="force stub mode (no LLM)")
    p.add_argument("--out", default=None, help="write JSON to file instead of stdout")
    p.add_argument(
        "--html",
        nargs="?",
        const="",
        default=None,
        help=(
            "write a human review HTML page. Pass a path, or omit the value "
            "to use <course_id>_review.html"
        ),
    )
    args = p.parse_args()

    if args.request:
        req = CourseRequest.model_validate_json(
            Path(args.request).read_text(encoding="utf-8")
        )
    else:
        missing = [
            name
            for name, value in {
                "--subject": args.subject,
                "--age": args.age,
                "--topic": args.topic,
            }.items()
            if value is None
        ]
        if missing:
            p.error("required unless --request is used: " + ", ".join(missing))
        req = CourseRequest(
            subject=Subject(args.subject),
            age_bracket=AgeBracket(args.age),
            topic=args.topic,
            learning_objectives=args.objective,
            design_requirements=args.requirement,
            max_modules=args.modules,
            planning_mode=PlanningMode(args.mode),
        )
    spec = plan_course(req, use_llm=False if args.stub else None)
    payload = spec.model_dump_json(indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(payload)
        print(f"course spec written to {args.out}", file=sys.stderr)
    else:
        print(payload)
    if args.html is not None:
        html_path = (
            Path(args.html)
            if args.html
            else Path(f"{spec.course_id}_review.html")
        )
        written_path = write_course_spec_html(spec, html_path)
        print(
            f"course review page written to {written_path.as_uri()}",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
