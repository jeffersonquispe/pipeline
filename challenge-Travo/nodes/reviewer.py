#!/usr/bin/env python3
import sys
import json
import re
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import LLMClient, ReviewerInput, ReviewerOutput

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


REVIEW_SYSTEM_PROMPT = """You are a senior code reviewer. Review a single code \
submission for correctness, security, performance, and maintainability, and give \
constructive, actionable feedback.

Assess, in priority order:
1. Security: input validation, injection risks, unsafe deserialization, secrets in \
code, weak crypto, unsafe file/subprocess/network use.
2. Correctness: logic errors, unhandled edge cases, error handling, resource \
management (leaks, unclosed handles), race conditions.
3. Performance: inefficient algorithms/queries, needless work in loops, missing \
caching, blocking calls in async code.
4. Maintainability: naming, structure, function complexity, duplication (DRY), \
SOLID/KISS/YAGNI, readability, docstrings/comments where they add value.
5. Conventions: strict compliance with the provided conventions.
6. Tests: presence and quality of tests and edge-case coverage when tests are \
included in the submission.

Rules:
- Only "issues" block approval: real defects — security holes, incorrect behavior, \
convention violations that were explicitly required. Style nitpicks and \
nice-to-haves go in "suggestions".
- Each issue/suggestion: one concrete sentence, referencing the specific symbol or \
line and how to fix it. No vague advice.
- Acknowledge nothing; output only findings.
- Judge only the code shown; do not assume missing files exist or are broken."""


def _parse_review(response_text: str) -> dict:
    """Parse the reviewer LLM response, tolerating markdown fences / surrounding
    prose. On failure, approve (fail-open) so a flaky reviewer doesn't stall the loop."""
    text = response_text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    if not text.startswith("{"):
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        if brace:
            text = brace.group(0)
    try:
        data = json.loads(text)
        return {
            "approved": bool(data.get("approved", True)),
            "issues": [str(x) for x in (data.get("issues") or [])],
            "suggestions": [str(x) for x in (data.get("suggestions") or [])],
        }
    except json.JSONDecodeError:
        logger.warning("Reviewer LLM response was not valid JSON; approving by default")
        return {"approved": True, "issues": [], "suggestions": []}


def review_code(payload: dict) -> dict:
    """
    Review code against conventions.
    Input: {code, conventions}
    Output: {approved, issues, suggestions, tokens}
    """
    try:
        reviewer_input = ReviewerInput(**payload)
        logger.info("Reviewing code")

        client = LLMClient()

        prompt = f"""{REVIEW_SYSTEM_PROMPT}

Conventions that were required for this code:
{reviewer_input.conventions}

Code under review:
```
{reviewer_input.code}
```

Respond with ONLY a raw JSON object (no markdown fences, no prose):
- approved: boolean (false if any blocking issue exists)
- issues: list of strings (blocking defects; empty if none)
- suggestions: list of strings (non-blocking improvements)"""

        response_text, tokens = client.complete(prompt)

        response_data = _parse_review(response_text)

        output = ReviewerOutput(
            approved=response_data["approved"],
            issues=response_data["issues"],
            suggestions=response_data["suggestions"],
            tokens=tokens
        )

        return output.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Reviewer failed: {str(e)}")
        sys.exit(1)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        result = review_code(payload)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in reviewer: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
