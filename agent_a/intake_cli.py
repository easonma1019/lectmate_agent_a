"""CLI for the course-design intake chatbot."""
from __future__ import annotations

import argparse
import sys

from .intake import IntakeResult, render_intake_summary, run_intake, write_intake_request
from .planner import has_llm_api_key


def _print_turn_feedback(result: IntakeResult) -> None:
    print("\n--- Intake status ---")
    print(f"Ready: {'yes' if result.ready else 'no'}")
    print(f"Confidence: {result.confidence}")
    if result.summary:
        print(f"Summary: {result.summary}")
    if result.request is not None:
        req = result.request
        print("Current draft:")
        print(f"- subject: {req.subject.value}")
        print(f"- age_bracket: {req.age_bracket.value}")
        print(f"- topic: {req.topic}")
        print(f"- planning_mode: {req.planning_mode.value}")
        print(f"- max_modules: {req.max_modules}")
        if req.design_requirements:
            print("- design_requirements:")
            for item in req.design_requirements:
                print(f"  - {item}")
    if result.follow_up_questions:
        print("Follow-up questions:")
        for question in result.follow_up_questions:
            print(f"- {question}")
    print("---------------------\n")


def _interactive_result(use_llm: bool) -> IntakeResult:
    print(
        "Course design intake. Type one message per turn. "
        "Type 'confirm' to save when ready, or an empty line to summarize and exit.",
        file=sys.stderr,
    )
    messages = []
    latest_result: IntakeResult | None = None
    while True:
        try:
            message = input("> ").strip()
        except EOFError:
            break
        if message.lower() in {"confirm", "确认"}:
            if latest_result is None:
                latest_result = run_intake(messages, use_llm=use_llm)
            return latest_result
        if not message:
            break
        if message.lower() in {"quit", "exit", "退出"}:
            break
        messages.append(message)
        latest_result = run_intake(messages, use_llm=use_llm)
        _print_turn_feedback(latest_result)
    if latest_result is not None:
        return latest_result
    return run_intake(messages, use_llm=use_llm)


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

    use_llm = not args.stub
    if use_llm and not has_llm_api_key():
        print(
            "OPENAI_API_KEY is not set; falling back to --stub intake.",
            file=sys.stderr,
        )
        use_llm = False

    messages = list(args.message)
    if not messages and not args.interactive:
        parser.error("provide at least one --message or use --interactive")

    result = (
        _interactive_result(use_llm)
        if args.interactive
        else run_intake(messages, use_llm=use_llm)
    )
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
