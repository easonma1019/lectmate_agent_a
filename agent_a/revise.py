"""CLI for revising an existing CourseSpec JSON file."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .reviser import (
    load_course_spec,
    revise_course_spec,
    write_course_spec_json,
    write_revision_report,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Revise an existing LectMate CourseSpec."
    )
    parser.add_argument("--in", dest="input_path", required=True, help="old spec.json")
    parser.add_argument(
        "--change",
        action="append",
        required=True,
        help="repeatable revision request",
    )
    parser.add_argument("--out", required=True, help="new revised spec JSON")
    parser.add_argument("--html", default=None, help="new revised review HTML")
    parser.add_argument(
        "--report",
        default=None,
        help="revision report markdown path",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=1,
        help="maximum revise-review rounds",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="use deterministic local revision and rule reviewer",
    )
    parser.add_argument(
        "--no-llm-reviewer",
        action="store_true",
        help="skip the LLM reviewer and use rule checks only",
    )
    args = parser.parse_args()

    change_request = "\n".join(args.change)
    old_spec = load_course_spec(args.input_path)
    use_llm = not args.stub
    if use_llm and not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "OPENROUTER_API_KEY is not set; falling back to --stub revision.",
            file=sys.stderr,
        )
        use_llm = False

    use_llm_reviewer = (
        use_llm
        and not args.no_llm_reviewer
        and bool(os.environ.get("OPENROUTER_API_KEY"))
    )

    result = revise_course_spec(
        old_spec,
        change_request,
        use_llm=use_llm,
        use_llm_reviewer=use_llm_reviewer,
        max_rounds=args.max_rounds,
        html_path=args.html,
    )
    json_path = write_course_spec_json(result.new_spec, args.out)
    print(f"revised course spec written to {json_path}", file=sys.stderr)
    if result.html_path is not None:
        print(
            f"revised course review page written to {result.html_path.as_uri()}",
            file=sys.stderr,
        )

    if args.report:
        report_path = write_revision_report(result, Path(args.report))
        print(f"revision report written to {report_path}", file=sys.stderr)

    return 0 if result.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
