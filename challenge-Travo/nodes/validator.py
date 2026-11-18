#!/usr/bin/env python3
import sys
import json
import logging
import ast
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import ValidatorInput, ValidatorOutput

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


def validate_code(payload: dict) -> dict:
    """
    Validate code syntax and basic structure.
    Input: {code, language}
    Output: {passed, errors, warnings, tokens?}
    """
    try:
        validator_input = ValidatorInput(**payload)
        logger.info(f"Validating {validator_input.language} code")

        errors = []
        warnings = []

        if validator_input.language == "python":
            errors, warnings = validate_python(validator_input.code)
        elif validator_input.language in ["javascript", "typescript"]:
            errors, warnings = validate_javascript(validator_input.code)

        output = ValidatorOutput(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            tokens=None
        )

        return output.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Validator failed: {str(e)}")
        sys.exit(1)


def validate_python(code: str) -> tuple[list, list]:
    """Validate Python code syntax."""
    errors = []
    warnings = []

    try:
        ast.parse(code)
    except SyntaxError as e:
        errors.append(f"Syntax error on line {e.lineno}: {e.msg}")
    except Exception as e:
        errors.append(f"Parse error: {str(e)}")

    # Basic style checks
    lines = code.split("\n")
    for i, line in enumerate(lines, 1):
        if len(line) > 100:
            warnings.append(f"Line {i} exceeds 100 characters ({len(line)})")
        if line.strip() and not line.startswith(" " * 4) and i > 1:
            # Check indentation
            if line[0] == " " and line[:4] != "    " * (len(line) - len(line.lstrip())) // 4:
                warnings.append(f"Line {i}: inconsistent indentation (use 4 spaces)")

    return errors, warnings


def validate_javascript(code: str) -> tuple[list, list]:
    """Basic JavaScript validation (syntax check only via heuristics)."""
    errors = []
    warnings = []

    # Basic bracket matching
    brackets = {"(": ")", "{": "}", "[": "]"}
    stack = []
    for char in code:
        if char in brackets:
            stack.append(char)
        elif char in brackets.values():
            if not stack or brackets[stack[-1]] != char:
                errors.append("Mismatched brackets")
                break
            stack.pop()

    if stack:
        errors.append(f"Unclosed brackets: {stack}")

    return errors, warnings


def main():
    try:
        payload = json.loads(sys.stdin.read())
        result = validate_code(payload)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in validator: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
