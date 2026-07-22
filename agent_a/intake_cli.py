"""CLI for the course-design intake chatbot."""
from __future__ import annotations

import argparse
import os
import sys

from .intake import render_intake_summary, run_intake, write_intake_request


def _interactive_messages() -> list[str]:
    print(
        "Course design intake. Type one message per turn. "
        "Submit an empty line when ready to summarize.",
        file=sys.stderr,
    )
    messages = []
    while True:
        try:
            message = input("> ").strip()
        except EOFError:
            break
        if not message:
            break
        messages.append(message)
    return messages


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clarify course-design needs before generating CourseSpec."
    )
    parser.add_argument(
        "--message",
        action="append",
        default=[],
        help="repeatable course-designer message",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="collect messages from stdin interactively",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="write confirmed CourseRequest JSON when intake is ready",
    )
    parser.add_argument(
        "--stub",
        action="store_true",
        help="use deterministic local extraction instead of the LLM",
    )
    args = parser.parse_args()

    messages = list(args.message)
    if args.interactive:
        messages.extend(_interactive_messages())
    if not messages:
        parser.error("provide at least one --message or use --interactive")

    use_llm = not args.stub
    if use_llm and not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "OPENROUTER_API_KEY is not set; falling back to --stub intake.",
            file=sys.stderr,
        )
        use_llm = False

    result = run_intake(messages, use_llm=use_llm)
    print(render_intake_summary(result))

    if args.out:
        if not result.ready:
            print(
                "intake is not ready; answer the follow-up questions before writing CourseRequest.",
                file=sys.stderr,
            )
            return 2
        path = write_intake_request(result, args.out)
        print(f"course request written to {path}", file=sys.stderr)

    return 0 if result.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
