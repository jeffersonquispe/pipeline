#!/usr/bin/env python3
"""
Quick demo script to test the pipeline orchestrator.
Run this to verify the complete flow without needing the HTTP server.
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from orchestrator.pipeline import PipelineStore
from orchestrator.queue_manager import QueueManager
from orchestrator.token_budget import TokenBudgetManager
from orchestrator.worker import Worker


async def main():
    print("Initializing orchestrator components...")
    pipeline_store = PipelineStore()
    queue_manager = QueueManager()
    budget_manager = TokenBudgetManager()
    worker = Worker(pipeline_store, queue_manager, budget_manager)

    print("Creating a test pipeline...")
    pipeline = await pipeline_store.create(
        project_id="demo-project",
        requirement="Build a temperature converter function"
    )

    print(f"Pipeline ID: {pipeline.id}")
    print(f"Status: {pipeline.status}")

    print("\nRunning pipeline...")
    try:
        # Acquire slot for demo
        await queue_manager.acquire_slot()

        # Run the pipeline (this will execute all nodes)
        success = await worker.run_pipeline(pipeline.id)

        print(f"Pipeline completed: {'SUCCESS' if success else 'FAILED'}")

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

    # Print results
    pipeline = await pipeline_store.get(pipeline.id)
    print(f"\nFinal status: {pipeline.status}")
    print(f"History entries: {len(pipeline.history)}")
    print(f"Attempt entries: {len(pipeline.attempts)}")

    # Print budget report
    report = budget_manager.get_report("demo-project")
    print(f"\nToken usage: {report.total_tokens} tokens")
    print(f"Estimated cost: ${report.total_cost_usd:.4f}")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
