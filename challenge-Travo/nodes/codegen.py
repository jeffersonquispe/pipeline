#!/usr/bin/env python3
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import LLMClient, CodegenInput, CodegenOutput

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


def generate_code(payload: dict) -> dict:
    """
    Generate code for a task.
    Input: {task, stack, conventions, feedback?}
    Output: {code, language, task_id, tokens}
    """
    try:
        codegen_input = CodegenInput(**payload)
        logger.info(f"Generating code for task {codegen_input.task.id}")

        client = LLMClient()

        feedback_context = ""
        if codegen_input.feedback:
            feedback_context = f"\n\nPrevious feedback to address:\n" + "\n".join(
                f"- {f}" for f in codegen_input.feedback
            )

        prompt = f"""You are an expert code generator. Generate clean, production-ready code for the following task.

Task: {codegen_input.task.description}
Task ID: {codegen_input.task.id}
Stack: {codegen_input.stack}
Conventions: {codegen_input.conventions}
{feedback_context}

Generate only the code without explanations or markdown blocks. The code should follow the conventions strictly."""

        code, tokens = client.complete(prompt)

        # Detect language from stack
        language = "python"
        if "javascript" in codegen_input.stack.lower() or "node" in codegen_input.stack.lower():
            language = "javascript"
        elif "typescript" in codegen_input.stack.lower():
            language = "typescript"

        output = CodegenOutput(
            code=code.strip(),
            language=language,
            task_id=codegen_input.task.id,
            tokens=tokens
        )

        return output.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Codegen failed: {str(e)}")
        sys.exit(1)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        result = generate_code(payload)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in codegen: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
