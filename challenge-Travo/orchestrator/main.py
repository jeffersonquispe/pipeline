import sys
import asyncio

# Windows requires ProactorEventLoop to support asyncio subprocesses.
# The default SelectorEventLoop does NOT support create_subprocess_exec.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from datetime import datetime

from .pipeline import PipelineStore
from .queue_manager import QueueManager
from .token_budget import TokenBudgetManager
from .worker import Worker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize components
pipeline_store = PipelineStore()
queue_manager = QueueManager()
budget_manager = TokenBudgetManager()
worker = Worker(pipeline_store, queue_manager, budget_manager)

app = FastAPI(title="AI Pipeline Orchestrator", version="1.0.0")


class CreatePipelineRequest(BaseModel):
    requirement: str
    project_id: str


class PipelineStatusResponse(BaseModel):
    id: str
    status: str
    active_node: str = None
    queue_position: int = -1
    history_count: int = 0
    attempt_count: int = 0


@app.on_event("startup")
async def startup():
    """Start background workers."""
    logger.info("Orchestrator starting up")
    logger.info(f"Event loop: {type(asyncio.get_event_loop()).__name__}")
    asyncio.create_task(worker_loop())


async def worker_loop():
    """Background task that processes queued pipelines."""
    logger.info("Worker loop started")
    while True:
        try:
            # Dequeue next pipeline (blocks until one is available)
            pipeline_id = await queue_manager.dequeue()
            logger.info(f"Dequeued pipeline {pipeline_id}")

            # Acquire execution slot (respects MAX_CONCURRENT_PIPELINES)
            await queue_manager.acquire_slot()

            # Run pipeline — use create_task so worker_loop can pick up the next item
            task = asyncio.create_task(worker.run_pipeline(pipeline_id))

            def _on_done(t: asyncio.Task):
                if t.cancelled():
                    logger.info(f"Pipeline task {pipeline_id} cancelled")
                    return
                exc = t.exception()
                if exc:
                    logger.error(f"Pipeline task {pipeline_id} raised: {exc}", exc_info=exc)

            task.add_done_callback(_on_done)

        except Exception as e:
            logger.error(f"Worker loop error: {str(e)}", exc_info=True)
            await asyncio.sleep(1)


@app.on_event("shutdown")
async def shutdown():
    """Kill any in-flight node subprocesses so they don't outlive the orchestrator."""
    logger.info("Orchestrator shutting down; terminating live nodes")
    worker.kill_all_nodes()


@app.post("/pipelines")
async def create_pipeline(request: CreatePipelineRequest):
    """Create a new pipeline."""
    try:
        # Create pipeline in store
        pipeline = await pipeline_store.create(
            project_id=request.project_id,
            requirement=request.requirement
        )

        # Try to enqueue
        enqueued = await queue_manager.enqueue(pipeline.id)

        if not enqueued:
            # Queue is over capacity
            position = await queue_manager.get_position(pipeline.id)
            return JSONResponse(
                status_code=503,
                content={
                    "error": "Service overloaded",
                    "pipeline_id": pipeline.id,
                    "queue_position": position
                }
            )

        logger.info(f"Created pipeline {pipeline.id} for project {request.project_id}")

        return {
            "id": pipeline.id,
            "status": "QUEUED",
            "created_at": pipeline.created_at.isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to create pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str):
    """Get pipeline status and history."""
    try:
        pipeline = await pipeline_store.get(pipeline_id)

        if not pipeline:
            raise HTTPException(status_code=404, detail="Pipeline not found")

        # Get queue position if queued
        queue_position = -1
        if pipeline.status == "QUEUED":
            queue_position = await queue_manager.get_position(pipeline_id)

        return {
            "id": pipeline.id,
            "project_id": pipeline.project_id,
            "requirement": pipeline.requirement,
            "status": pipeline.status,
            "active_node": pipeline.active_node,
            "queue_position": queue_position,
            "created_at": pipeline.created_at.isoformat(),
            "completed_at": pipeline.completed_at.isoformat() if pipeline.completed_at else None,
            "history": [
                {
                    "node": h.node,
                    "attempt": h.attempt,
                    "timestamp": h.timestamp.isoformat(),
                    "duration_ms": h.duration_ms,
                    "success": h.success,
                    "input_keys": list(h.input.keys()),
                    "output_keys": list(h.output.keys())
                }
                for h in pipeline.history
            ],
            "attempts": [
                {
                    "attempt_n": a.attempt_n,
                    "node": a.node,
                    "reasons": a.reasons,
                    "timestamp": a.timestamp.isoformat()
                }
                for a in pipeline.attempts
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/metrics")
async def get_metrics():
    """Get system metrics."""
    try:
        pipelines = await pipeline_store.list_all()

        # Count by status
        status_counts = {}
        for pipeline in pipelines:
            status = pipeline.status.split(":")[0]  # Remove node suffix
            status_counts[status] = status_counts.get(status, 0) + 1

        # Calculate correction loop success rate
        total_attempts = sum(len(p.attempts) for p in pipelines)
        successful_pipelines = len(await pipeline_store.get_by_status("COMPLETED"))
        avg_attempts = (
            total_attempts / successful_pipelines
            if successful_pipelines > 0
            else 0
        )

        # Collect token usage by project
        project_costs = {}
        for project_id in set(p.project_id for p in pipelines):
            report = budget_manager.get_report(project_id)
            project_costs[project_id] = {
                "total_tokens": report.total_tokens,
                "total_cost_usd": report.total_cost_usd,
                "breakdown": report.breakdown
            }

        # Calculate average node duration
        all_durations = {}
        for pipeline in pipelines:
            for history in pipeline.history:
                if history.node not in all_durations:
                    all_durations[history.node] = []
                all_durations[history.node].append(history.duration_ms)

        avg_durations = {
            node: sum(durations) // len(durations)
            for node, durations in all_durations.items()
        }

        # Queue status
        queue_status = queue_manager.get_queue_status()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "pipelines": {
                "by_status": status_counts,
                "total": len(pipelines)
            },
            "correction_loop": {
                "avg_attempts_to_approval": round(avg_attempts, 2),
                "successful_pipelines": successful_pipelines
            },
            "costs": project_costs,
            "node_durations_ms": avg_durations,
            "queue": queue_status
        }

    except Exception as e:
        logger.error(f"Failed to get metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
