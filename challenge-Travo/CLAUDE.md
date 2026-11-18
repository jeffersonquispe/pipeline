# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**AI Pipeline Orchestrator** — A senior-level technical assessment for Trazo (software factory). Implements an autonomous pipeline that takes requirements → plans → generates code → reviews → validates → delivers, with built-in auto-correction loops and cost tracking.

**Key principle**: Each stage is an independent CLI (subprocess execution via JSON stdin/stdout). The orchestrator (FastAPI + asyncio) coordinates execution, manages queues, enforces quality gates, and tracks LLM token costs.

## Stack & Architecture

- **Language**: Python 3.11+
- **Framework**: FastAPI + Uvicorn (HTTP API), asyncio (concurrency)
- **LLM**: Anthropic/OpenAI SDKs with mock fallback (LLM_MOCK=true by default)
- **State**: In-memory `PipelineStore` with `asyncio.Lock` for thread-safe access
- **Queue**: `asyncio.Queue` + semaphore-based backpressure

**Critical architectural patterns:**

1. **CLI nodes as subprocesses**: planner, codegen, reviewer, validator, delivery
2. **JSON contracts**: Each node reads stdin, writes stdout JSON
3. **Auto-correction loop**: codegen → reviewer → validator with feedback cycling (max 3 attempts)
4. **LLM rate limiting**: Global semaphore (`MAX_LLM_CALLS`) in orchestrator worker
5. **Token budget tracking**: `TokenBudgetManager` calculates per-project LLM costs

## Common Tasks

### Run the orchestrator
```bash
uvicorn orchestrator.main:app --reload
```

### Test a single node
```bash
echo '{"requirement": "...", "project_id": "p1"}' | python nodes/planner.py
```

### Submit a pipeline via API
```bash
curl -X POST http://localhost:8000/pipelines \
  -H "Content-Type: application/json" \
  -d '{"requirement": "Build a login module", "project_id": "p1"}'
```

### View pipeline status & history
```bash
curl http://localhost:8000/pipelines/{pipeline_id}
```

### View system metrics (costs, success rates, node durations)
```bash
curl http://localhost:8000/metrics
```

### Configure environment
Copy `.env.example` to `.env` and edit:
- `LLM_MOCK=true` for testing (no API calls)
- `LLM_PROVIDER=anthropic` or `openai`
- `MAX_CORRECTION_ATTEMPTS=3` to adjust retry limit
- `TOKEN_BUDGET_ALERT_USD=10.0` for cost alerts

## File Structure

```
nodes/                      # CLI nodes (subprocess-executed)
  planner.py               # Decompose requirement → tasks
  codegen.py               # Generate code (with feedback loop)
  reviewer.py              # Code review against conventions
  validator.py             # Syntax/style validation
  delivery.py              # Write artifacts to disk

orchestrator/               # FastAPI orchestrator
  main.py                  # HTTP endpoints (/pipelines, /metrics, /health)
  worker.py ★              # Pipeline execution engine + auto-correction loop
  pipeline.py              # PipelineStore (async state management)
  queue_manager.py         # Queue + concurrency control + backpressure
  token_budget.py          # LLM cost tracking & budget alerts

shared/                     # Shared utilities
  models.py                # Pydantic models for all node contracts
  llm_client.py            # LLM abstraction (mock/Anthropic/OpenAI)

★ = most complex, read first for full architecture understanding
```

## Design Decisions

See **README.md** for detailed answers to the 5 evaluation questions:

1. **Why CLIs instead of classes?** Process isolation, Unix composability, language agility
2. **State management?** JSON contracts + in-memory PipelineStore with asyncio.Lock
3. **Semaphore placement?** In `worker.run_node()` before subprocess, centralizes rate limit
4. **3-fail escalation?** Error classification → adaptive prompting → human webhook escalation
5. **500 concurrent scaling?** Redis queue + persistent DB + distributed workers + HTTP nodes

## Key Implementation Details

### Auto-Correction Loop (worker.py:run_correction_loop)

```python
for attempt in 1..MAX_ATTEMPTS:
    1. codegen(task, stack, conventions, feedback?)
    2. reviewer(code, conventions)
       - if not approved: feedback = issues, continue
    3. validator(code, language)
       - if not passed: feedback = errors, continue
    4. All passed → return True
    
# Log each attempt with reasons, delta vs previous
```

**Important**: Feedback is accumulated from both reviewer and validator. Each retry is logged with attempt number and reasons for failure.

### Node Contract (stdin/stdout JSON)

Each node:
- Reads JSON from stdin
- Processes
- Writes JSON to stdout (exit 0 success, exit 1 failure)
- Logs to stderr

Example:
```bash
echo '{"requirement": "...", "project_id": "p1"}' | python nodes/planner.py
# stdout: {"tasks": [...], "stack": "...", "conventions": "...", "tokens": {...}}
# stderr: [INFO] Planning requirement...
```

### Token Cost Tracking

`TokenBudgetManager.record()` is called after every LLM node execution:
- Extracts `{input, output, model}` from node output
- Calculates USD cost based on `PRICES[model]`
- Alerts if project exceeds `TOKEN_BUDGET_ALERT_USD` threshold

Cost report available via `/metrics`.

### Queue Backpressure

When queue size exceeds `QUEUE_BACKPRESSURE_THRESHOLD`:
- POST /pipelines returns HTTP 503 (Service Unavailable)
- Includes queue position so client can retry
- Prevents memory overload on orchestrator

## Testing Strategy

1. **Unit test nodes individually**: `echo '...' | python nodes/X.py`
2. **Test pipeline flow**: Mock the entire loop locally
3. **Test API endpoints**: curl or Postman
4. **Test concurrency**: Submit multiple pipelines, watch `/metrics`
5. **Test error paths**: Inspect `/pipelines/{id}` history for failed attempts

## Common Gotchas

1. **Nodes must be executable from project root**: `python nodes/{name}.py` assumes CWD is project root
2. **LLM calls in mock mode are deterministic**: Good for testing, but don't expect LLM variability
3. **In-memory store loses data on restart**: OK for evaluation; use PostgreSQL + Redis for production
4. **Subprocess communication is blocking**: asyncio.create_subprocess_exec wraps it properly; don't use subprocess.run
5. **Semaphore acquired before subprocess**: LLM-heavy nodes block at orchestrator layer, not at individual LLM provider

## Debugging

- **Check logs**: Look at stderr from `uvicornV` process for worker/node logs
- **Inspect pipeline state**: GET `/pipelines/{id}` shows full history and attempt logs
- **Test node in isolation**: `echo '...' | python nodes/X.py 2>stderr.log` to debug individual node
- **Enable mock mode**: Set `LLM_MOCK=true` to bypass API calls and test architecture
- **Check budget**: GET `/metrics` shows token costs per project

## When to Modify Each Component

| File | When to Modify | Example |
|------|---|---|
| `nodes/*.py` | Add new stage, change node logic | Add syntax checking before reviewer |
| `worker.py` | Change loop logic, auto-correction strategy | Implement adaptive prompting for error types |
| `pipeline.py` | Change state schema | Add checkpoints, pipeline versioning |
| `queue_manager.py` | Adjust concurrency control | Change backpressure threshold strategy |
| `token_budget.py` | Add pricing tiers, alerting logic | Support reserved capacity pricing |
| `main.py` | Add endpoints, change API contract | Add webhook escalation endpoint |
| `models.py` | Update node I/O contracts | Add new field to planner output |

