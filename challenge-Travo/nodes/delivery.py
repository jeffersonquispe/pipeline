#!/usr/bin/env python3
import sys
import json
import logging
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import DeliveryInput, DeliveryOutput

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)


def deliver_artifact(payload: dict) -> dict:
    """
    Deliver code artifact to storage.
    Input: {code, task_id, project_id}
    Output: {status, artifact_path}
    """
    try:
        delivery_input = DeliveryInput(**payload)
        logger.info(f"Delivering artifact for task {delivery_input.task_id} in project {delivery_input.project_id}")

        # Create directory structure
        artifacts_dir = os.getenv("ARTIFACTS_DIR", "./artifacts")
        project_dir = Path(artifacts_dir) / delivery_input.project_id
        project_dir.mkdir(parents=True, exist_ok=True)

        # Determine file extension based on common patterns
        ext = "py"
        if "javascript" in delivery_input.code.lower() or "const " in delivery_input.code:
            ext = "js"
        elif "typescript" in delivery_input.code.lower():
            ext = "ts"

        # Write artifact
        artifact_file = project_dir / f"{delivery_input.task_id}.{ext}"
        artifact_file.write_text(delivery_input.code)

        output = DeliveryOutput(
            status="delivered",
            artifact_path=str(artifact_file)
        )

        logger.info(f"Artifact delivered to {artifact_file}")
        return output.model_dump(mode="json")

    except Exception as e:
        logger.error(f"Delivery failed: {str(e)}")
        sys.exit(1)


def main():
    try:
        payload = json.loads(sys.stdin.read())
        result = deliver_artifact(payload)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in delivery: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
