"""
Prerequisite concept graph (pilot: Coding / Python).

A small, hand-curated DAG of core concepts that the planner consults so
module ordering is never accidentally out of sequence (Game Plan §5,
'Techniques worth trying'). The LLM proposes an ordering; this graph is the
ground truth the validator checks it against.

Grounding: CSTA 2017 progression (sequences -> loops -> variables ->
conditionals -> functions -> data structures) — this IS the 'set of rules /
anchors' the company asked for in the 2 Jul meeting.
"""
from __future__ import annotations

# concept -> concepts it depends on
PYTHON_CONCEPTS: dict[str, list[str]] = {
    "what_is_a_program": [],
    "sequences_and_instructions": ["what_is_a_program"],
    "variables": ["sequences_and_instructions"],
    "input_output": ["variables"],
    "operators_and_expressions": ["variables"],
    "conditionals": ["operators_and_expressions"],
    "loops": ["conditionals"],
    "lists": ["loops"],
    "functions": ["loops"],
    "dictionaries": ["lists"],
    "error_handling": ["functions"],
    "file_io": ["functions"],
    "modules_and_libraries": ["functions"],
    "classes_and_objects": ["functions", "lists"],
    "apis_and_requests": ["modules_and_libraries", "dictionaries"],
    "testing_and_debugging": ["functions"],
    "version_control": [],
    "code_review_practice": ["testing_and_debugging", "version_control"],
}


def toposort_check(order: list[str], graph: dict[str, list[str]] = PYTHON_CONCEPTS) -> list[str]:
    """Return a list of violation messages for a proposed concept ordering.
    Unknown concepts are ignored (the LLM may introduce topic-specific ones)."""
    problems: list[str] = []
    seen: set[str] = set()
    for c in order:
        for dep in graph.get(c, []):
            if dep in order and dep not in seen:
                problems.append(f"'{c}' is scheduled before its prerequisite '{dep}'")
        seen.add(c)
    return problems
