"""CLI: python -m agent_a.cli --subject Coding --age "Creators (10-13)" --topic "Python fundamentals" """
from __future__ import annotations

import argparse
import json
import sys

from .planner import plan_course
from .schemas import AgeBracket, CourseRequest, Subject


def main() -> int:
    p = argparse.ArgumentParser(description="Agent A — Curriculum Architect")
    p.add_argument("--subject", required=True, choices=[s.value for s in Subject])
    p.add_argument("--age", required=True, choices=[a.value for a in AgeBracket])
    p.add_argument("--topic", required=True)
    p.add_argument("--objective", action="append", default=[], help="repeatable")
    p.add_argument("--modules", type=int, default=None)
    p.add_argument("--stub", action="store_true", help="force stub mode (no LLM)")
    p.add_argument("--out", default=None, help="write JSON to file instead of stdout")
    args = p.parse_args()

    req = CourseRequest(
        subject=Subject(args.subject),
        age_bracket=AgeBracket(args.age),
        topic=args.topic,
        learning_objectives=args.objective,
        max_modules=args.modules,
    )
    spec = plan_course(req, use_llm=False if args.stub else None)
    payload = spec.model_dump_json(indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(payload)
        print(f"course spec written to {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
