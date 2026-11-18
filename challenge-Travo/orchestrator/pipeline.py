import asyncio
import uuid
from datetime import datetime
from typing import Dict, Optional
from shared import Pipeline, PipelineHistory, PipelineAttempt


class PipelineStore:
    """In-memory store for pipeline state with async locking."""

    def __init__(self):
        self.pipelines: Dict[str, Pipeline] = {}
        self.lock = asyncio.Lock()

    async def create(self, project_id: str, requirement: str) -> Pipeline:
        """Create a new pipeline."""
        async with self.lock:
            pipeline = Pipeline(
                id=str(uuid.uuid4()),
                project_id=project_id,
                requirement=requirement,
                status="QUEUED",
            )
            self.pipelines[pipeline.id] = pipeline
            return pipeline

    async def get(self, pipeline_id: str) -> Optional[Pipeline]:
        """Get pipeline by ID."""
        async with self.lock:
            return self.pipelines.get(pipeline_id)

    async def update(self, pipeline_id: str, **kwargs) -> Optional[Pipeline]:
        """Update pipeline fields."""
        async with self.lock:
            if pipeline_id not in self.pipelines:
                return None

            pipeline = self.pipelines[pipeline_id]
            for key, value in kwargs.items():
                if hasattr(pipeline, key):
                    setattr(pipeline, key, value)

            self.pipelines[pipeline_id] = pipeline
            return pipeline

    async def add_history(self, pipeline_id: str, history: PipelineHistory) -> Optional[Pipeline]:
        """Add a history entry to the pipeline."""
        async with self.lock:
            if pipeline_id not in self.pipelines:
                return None

            pipeline = self.pipelines[pipeline_id]
            pipeline.history.append(history)
            self.pipelines[pipeline_id] = pipeline
            return pipeline

    async def add_attempt(self, pipeline_id: str, attempt: PipelineAttempt) -> Optional[Pipeline]:
        """Add an attempt entry to the pipeline."""
        async with self.lock:
            if pipeline_id not in self.pipelines:
                return None

            pipeline = self.pipelines[pipeline_id]
            pipeline.attempts.append(attempt)
            self.pipelines[pipeline_id] = pipeline
            return pipeline

    async def list_all(self) -> list[Pipeline]:
        """List all pipelines."""
        async with self.lock:
            return list(self.pipelines.values())

    async def get_by_status(self, status: str) -> list[Pipeline]:
        """Get pipelines filtered by status."""
        async with self.lock:
            return [p for p in self.pipelines.values() if p.status == status]
