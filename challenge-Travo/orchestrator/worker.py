import asyncio
import subprocess
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Project root directory (parent of orchestrator/)
_PROJECT_ROOT = Path(__file__).parent.parent

from shared import (
    PipelineHistory,
    PipelineAttempt,
    Task,
    TokenUsage,
)
from .pipeline import PipelineStore
from .queue_manager import QueueManager
from .token_budget import TokenBudgetManager

logger = logging.getLogger(__name__)


class Worker:
    """Execute pipeline tasks with auto-correction loop."""

    def __init__(
        self,
        pipeline_store: PipelineStore,
        queue_manager: QueueManager,
        budget_manager: TokenBudgetManager,
    ):
        self.pipeline_store = pipeline_store
        self.queue_manager = queue_manager
        self.budget_manager = budget_manager
        self.max_attempts = int(os.getenv("MAX_CORRECTION_ATTEMPTS", "3"))
        self.llm_semaphore = asyncio.Semaphore(
            int(os.getenv("MAX_LLM_CALLS", "10"))
        )
        # Track live node subprocesses so they can be killed on shutdown.
        self._live_procs: set[subprocess.Popen] = set()

    async def run_pipeline(self, pipeline_id: str) -> bool:
        """
        Execute full pipeline: planner → task loop → delivery.
        Returns True if successful, False otherwise.
        """
        try:
            pipeline = await self.pipeline_store.get(pipeline_id)
            if not pipeline:
                logger.error(f"Pipeline {pipeline_id} not found")
                return False

            # Update status to RUNNING
            await self.pipeline_store.update(
                pipeline_id,
                status="RUNNING:planner",
                active_node="planner"
            )

            # Step 1: Run planner
            planner_result = await self.run_node(
                "planner",
                {
                    "requirement": pipeline.requirement,
                    "project_id": pipeline.project_id
                },
                pipeline_id,
                attempt=1
            )

            if not planner_result:
                await self.pipeline_store.update(
                    pipeline_id,
                    status="FAILED",
                    active_node=None
                )
                return False

            # Extract tasks, stack, conventions
            tasks = [Task(**t) for t in planner_result.get("tasks", [])]
            stack = planner_result.get("stack", "")
            conventions = planner_result.get("conventions", "")

            logger.info(f"Planner generated {len(tasks)} tasks")

            # Step 2: For each task, run auto-correction loop
            for task in tasks:
                success = await self.run_correction_loop(
                    pipeline_id,
                    task,
                    stack,
                    conventions
                )

                if not success:
                    logger.warning(f"Task {task.id} failed after max attempts")
                    await self.pipeline_store.update(
                        pipeline_id,
                        status="FAILED",
                        active_node=None
                    )
                    return False

                # Step 3: Deliver approved code
                code = None
                # Retrieve last successful codegen output from history
                for hist in reversed(pipeline.history):
                    if hist.node == "codegen" and hist.success:
                        code = hist.output.get("code")
                        break

                if code:
                    delivery_result = await self.run_node(
                        "delivery",
                        {
                            "code": code,
                            "task_id": task.id,
                            "project_id": pipeline.project_id
                        },
                        pipeline_id,
                        attempt=1
                    )

                    if not delivery_result:
                        logger.warning(f"Delivery failed for task {task.id}")
                        # Continue to next task instead of failing entire pipeline

            # Mark as completed
            await self.pipeline_store.update(
                pipeline_id,
                status="COMPLETED",
                active_node=None,
                completed_at=datetime.utcnow()
            )

            logger.info(f"Pipeline {pipeline_id} completed successfully")
            return True

        except Exception as e:
            logger.error(f"Pipeline {pipeline_id} failed with error: {str(e)}")
            await self.pipeline_store.update(
                pipeline_id,
                status="FAILED",
                active_node=None
            )
            return False
        finally:
            self.queue_manager.release_slot()

    async def run_correction_loop(
        self,
        pipeline_id: str,
        task: Task,
        stack: str,
        conventions: str
    ) -> bool:
        """
        Run codegen → reviewer → validator loop with auto-correction.
        Returns True if code is approved and passes validation.
        """
        pipeline = await self.pipeline_store.get(pipeline_id)
        feedback = None

        for attempt in range(1, self.max_attempts + 1):
            logger.info(f"Correction loop attempt {attempt} for task {task.id}")

            # Step 1: Run codegen
            codegen_result = await self.run_node(
                "codegen",
                {
                    "task": task.model_dump(),
                    "stack": stack,
                    "conventions": conventions,
                    "feedback": feedback
                },
                pipeline_id,
                attempt=attempt
            )

            if not codegen_result:
                logger.warning(f"Codegen failed on attempt {attempt}")
                continue

            code = codegen_result.get("code", "")
            language = codegen_result.get("language", "python")

            # Step 2: Run reviewer
            reviewer_result = await self.run_node(
                "reviewer",
                {
                    "code": code,
                    "conventions": conventions
                },
                pipeline_id,
                attempt=attempt
            )

            if not reviewer_result:
                logger.warning(f"Reviewer failed on attempt {attempt}")
                continue

            approved = reviewer_result.get("approved", False)
            issues = reviewer_result.get("issues", [])

            if not approved:
                logger.info(f"Code rejected by reviewer on attempt {attempt}: {issues}")
                feedback = issues
                await self.pipeline_store.add_attempt(
                    pipeline_id,
                    PipelineAttempt(
                        attempt_n=attempt,
                        node="reviewer",
                        reasons=issues,
                        feedback=issues
                    )
                )
                continue

            # Step 3: Run validator
            validator_result = await self.run_node(
                "validator",
                {
                    "code": code,
                    "language": language
                },
                pipeline_id,
                attempt=attempt
            )

            if not validator_result:
                logger.warning(f"Validator failed on attempt {attempt}")
                continue

            passed = validator_result.get("passed", False)
            errors = validator_result.get("errors", [])

            if not passed:
                logger.info(f"Code failed validation on attempt {attempt}: {errors}")
                feedback = errors
                await self.pipeline_store.add_attempt(
                    pipeline_id,
                    PipelineAttempt(
                        attempt_n=attempt,
                        node="validator",
                        reasons=errors,
                        feedback=errors
                    )
                )
                continue

            # Success!
            logger.info(f"Code approved and validated on attempt {attempt}")
            return True

        # All attempts exhausted
        logger.error(f"Correction loop failed for task {task.id} after {self.max_attempts} attempts")
        return False

    async def run_node(
        self,
        node_name: str,
        input_data: Dict[str, Any],
        pipeline_id: str,
        attempt: int = 1
    ) -> Optional[Dict[str, Any]]:
        """
        Execute a node as a subprocess.
        Acquires LLM semaphore if node requires it.
        """
        start_time = time.time()
        pipeline = await self.pipeline_store.get(pipeline_id)

        # Acquire LLM semaphore for nodes that call LLM
        llm_nodes = ["planner", "codegen", "reviewer"]
        if node_name in llm_nodes:
            await self.llm_semaphore.acquire()

        try:
            await self.pipeline_store.update(pipeline_id, active_node=node_name)

            # Execute node as subprocess
            result = await asyncio.create_task(
                self._execute_subprocess(node_name, input_data)
            )

            duration_ms = int((time.time() - start_time) * 1000)

            # Record in history
            await self.pipeline_store.add_history(
                pipeline_id,
                PipelineHistory(
                    node=node_name,
                    attempt=attempt,
                    input=input_data,
                    output=result or {},
                    duration_ms=duration_ms,
                    success=result is not None
                )
            )

            # Record token usage if available
            if result and "tokens" in result and result["tokens"]:
                tokens_data = result["tokens"]
                token_usage = TokenUsage(**tokens_data)
                self.budget_manager.record(pipeline.project_id, node_name, token_usage)

            logger.info(f"Node {node_name} completed in {duration_ms}ms")
            return result

        except Exception as e:
            logger.error(f"Node {node_name} execution failed: {str(e)}")
            duration_ms = int((time.time() - start_time) * 1000)
            await self.pipeline_store.add_history(
                pipeline_id,
                PipelineHistory(
                    node=node_name,
                    attempt=attempt,
                    input=input_data,
                    output={"error": str(e)},
                    duration_ms=duration_ms,
                    success=False
                )
            )
            return None

        finally:
            if node_name in llm_nodes:
                self.llm_semaphore.release()

    def _execute_subprocess_sync(
        self,
        node_name: str,
        input_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Execute a node CLI as subprocess synchronously inside a thread."""
        proc = None
        try:
            proc = subprocess.Popen(
                [sys.executable, f"nodes/{node_name}.py"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(_PROJECT_ROOT)       # resolve nodes/ relative to project root
            )
            self._live_procs.add(proc)

            stdin_data = json.dumps(input_data).encode()
            stdout, stderr = proc.communicate(stdin_data)

            if proc.returncode != 0:
                error_msg = stderr.decode(errors="replace") if stderr else "Unknown error"
                logger.error(f"Node {node_name} exited with code {proc.returncode}: {error_msg}")
                return None

            try:
                result = json.loads(stdout.decode())
                return result
            except json.JSONDecodeError as e:
                raw = stdout.decode(errors="replace")[:200]
                logger.error(f"Failed to parse node {node_name} output: {str(e)} | raw: {raw}")
                return None

        except Exception as e:
            logger.error(f"Subprocess execution failed for node '{node_name}': {str(e)}")
            return None

        finally:
            if proc is not None:
                self._live_procs.discard(proc)

    async def _execute_subprocess(
        self,
        node_name: str,
        input_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Execute a node CLI as subprocess, safely run on a thread to support all event loops on Windows."""
        try:
            return await asyncio.to_thread(self._execute_subprocess_sync, node_name, input_data)
        except asyncio.CancelledError:
            # to_thread can't be cancelled; kill the node so the worker thread unblocks.
            self.kill_all_nodes()
            raise

    def kill_all_nodes(self) -> None:
        """Terminate any live node subprocesses (used on shutdown/cancellation)."""
        for proc in list(self._live_procs):
            if proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
