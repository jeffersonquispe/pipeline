import asyncio
import os
import logging

logger = logging.getLogger(__name__)


class QueueManager:
    """Manages pipeline queue with concurrency and backpressure control."""

    def __init__(self):
        self.max_concurrent = int(os.getenv("MAX_CONCURRENT_PIPELINES", "5"))
        self.backpressure_threshold = int(os.getenv("QUEUE_BACKPRESSURE_THRESHOLD", "20"))
        self.queue: asyncio.Queue = asyncio.Queue()
        self.active_pipelines = 0
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.lock = asyncio.Lock()

    async def enqueue(self, pipeline_id: str) -> bool:
        """
        Enqueue a pipeline.
        Returns False if backpressure threshold exceeded.
        """
        if self.queue.qsize() >= self.backpressure_threshold:
            logger.warning(
                f"Queue backpressure exceeded: {self.queue.qsize()} >= {self.backpressure_threshold}"
            )
            return False

        await self.queue.put(pipeline_id)
        logger.info(f"Enqueued pipeline {pipeline_id}, queue size: {self.queue.qsize()}")
        return True

    async def get_position(self, pipeline_id: str) -> int:
        """Get the position of a pipeline in the queue."""
        async with self.lock:
            items = list(self.queue._queue)
            if pipeline_id in items:
                return items.index(pipeline_id) + 1
            return -1

    async def dequeue(self) -> str:
        """Dequeue a pipeline. Blocks if queue is empty."""
        return await self.queue.get()

    async def acquire_slot(self) -> None:
        """Acquire a slot to run a pipeline. Blocks if max concurrent reached."""
        await self.semaphore.acquire()
        async with self.lock:
            self.active_pipelines += 1

    def release_slot(self) -> None:
        """Release a pipeline execution slot."""
        self.semaphore.release()
        # Note: active_pipelines is decremented by worker after slot is released

    async def wait_for_slot(self) -> None:
        """Wait until a slot is available."""
        while self.semaphore._value <= 0:
            await asyncio.sleep(0.1)

    def get_queue_status(self) -> dict:
        """Get queue status information."""
        return {
            "queue_size": self.queue.qsize(),
            "active_pipelines": self.active_pipelines,
            "max_concurrent": self.max_concurrent,
            "backpressure_threshold": self.backpressure_threshold,
            "semaphore_available": self.semaphore._value,
        }
