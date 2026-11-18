#!/usr/bin/env python3
import sys
import json
import re
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import LLMClient, PlannerInput, PlannerOutput, Task

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


def _as_text(value, default: str) -> str:
    """Coerce a plan field to a string; the LLM sometimes returns a dict/list."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "; ".join(f"{k}: {_as_text(v, '')}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(_as_text(v, "") for v in value)
    return str(value)


def _parse_plan(response_text: str, requirement: str) -> dict:
    """Parse the LLM plan, tolerating markdown fences; fall back to a
    single task that just forwards the raw requirement to codegen."""
    text = response_text.strip()

    # Strip ```json ... ``` or ``` ... ``` fences if present.
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()

    # Otherwise grab the first {...} block.
    if not text.startswith("{"):
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)

    try:
        data = json.loads(text)
        if data.get("tasks"):
            return data
    except json.JSONDecodeError:
        logger.warning("Planner LLM response was not valid JSON; using raw-requirement fallback")

    # Fallback: don't invent generic phases or a fake stack. Hand the whole
    # requirement to codegen as one task so the output still matches the ask.
    return {
        "tasks": [
            {"id": "task1", "description": requirement, "priority": "high"}
        ],
        "stack": "Python",
        "conventions": "PEP 8, type hints, docstrings",
    }


def plan_requirement(payload: dict) -> dict:
    """
    Parse requirement and generate task breakdown.
    Input: {requirement, project_id}
    Output: {tasks, stack, conventions, tokens}
    """
    try:
        planner_input = PlannerInput(**payload)
        logger.info(f"Planning requirement for project {planner_input.project_id}")

        client = LLMClient()
        prompt = f"""You are a technical architect. Break down the following requirement into concrete, implementable tasks.

Requirement: {planner_input.requirement}
Project ID: {planner_input.project_id}

Respond with ONLY a raw JSON object (no markdown fences, no prose) containing:
- tasks: list of {{id, description, priority}} where each description is a concrete,
  self-contained instruction specific to THIS requirement (not generic phases like
  "setup environment" or "implement core logic")
- stack: technology stack recommendation appropriate for this requirement
- conventions: code conventions to follow

Be concise and practical."""

        response_text, tokens = client.complete(prompt)

        response_data = _parse_plan(response_text, planner_input.requirement)

        tasks = []
        for i, t in enumerate(response_data.get("tasks", []), start=1):
            tasks.append(Task(
                id=str(t.get("id") or f"task{i}"),
                description=_as_text(t.get("description"), ""),
                priority=str(t.get("priority") or "medium"),
            ))
        if not tasks:
            tasks = [Task(id="task1", description=planner_input.requirement, priority="high")]

        output = PlannerOutput(
            tasks=tasks,
            stack=_as_text(response_data.get("stack"), "Python"),
            conventions=_as_text(response_data.get("conventions"), "PEP 8"),
            tokens=tokens
        )

        return output.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Planner failed: {str(e)}")
        sys.exit(1)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        result = plan_requirement(payload)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in planner: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
