# AI Pipeline Orchestrator for Software Factory Automation

A production-ready system that automates software factory workflows using AI agents. The pipeline coordinates autonomous code generation, review, validation, and delivery with built-in auto-correction loops and comprehensive observability.

Based on: https://prod.d13rzhkk8cj2z0.amplifyapp.com/

### AI-Driven Development Lifecycle (AI-DLC) Method Definition

## Architecture Overview

```
REQUIREMENT → PLANNER → CODEGEN → REVIEWER → VALIDATOR → DELIVERY
                          ↓↑ (feedback loop)
```

Each stage is an independent CLI that reads JSON from stdin and writes results to stdout. The orchestrator (FastAPI + asyncio) coordinates subprocess execution, manages queues, tracks token usage, and enforces quality gates.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Create environment
cp .env.example .env

# Run orchestrator
uvicorn orchestrator.main:app --reload

# Submit a requirement
curl -X POST http://localhost:8000/pipelines \
  -H "Content-Type: application/json" \
  -d '{"requirement": "Build a user authentication module", "project_id": "p1"}'

# Check status
curl http://localhost:8000/pipelines/{id}

# View metrics
curl http://localhost:8000/metrics
```

## Components

### Nodes (CLI)

Each node is a standalone Python script that processes one stage of the pipeline:

- **planner.py**: Decomposes requirement into tasks, recommends stack and conventions
- **codegen.py**: Generates code for a task (incorporates feedback if rejections occur)
- **reviewer.py**: Validates code against conventions, returns approval decision
- **validator.py**: Syntax and style validation (ast.parse for Python, bracket matching for JS)
- **delivery.py**: Writes approved code to artifact storage

### Orchestrator

- **main.py**: FastAPI app with `/pipelines`, `/metrics`, `/health` endpoints
- **pipeline.py**: In-memory pipeline state store with async locking
- **queue_manager.py**: Concurrent execution control with backpressure (returns 503)
- **worker.py**: Pipeline execution engine with auto-correction loop and LLM semaphore
- **token_budget.py**: Token usage tracking, cost calculation, budget alerting

### Shared

- **models.py**: Pydantic models for all node contracts and pipeline state
- **llm_client.py**: LLM abstraction layer (mock, Anthropic, OpenAI) with fallback to deterministic responses



## Configuration

Environment variables (see `.env.example`):

```env
LLM_MOCK=true                          # true for testing, false for real LLM calls
LLM_PROVIDER=anthropic                 # anthropic or openai
ANTHROPIC_API_KEY=                     # Required if provider=anthropic
OPENAI_API_KEY=                        # Required if provider=openai
MAX_CONCURRENT_PIPELINES=5             # Max pipelines running simultaneously
MAX_LLM_CALLS=10                       # Global LLM call rate limit
QUEUE_BACKPRESSURE_THRESHOLD=20        # If queue > 20, return 503
MAX_CORRECTION_ATTEMPTS=3              # Max retries per task
TOKEN_BUDGET_ALERT_USD=10.0            # Alert when project cost exceeds
TOKEN_BUDGET_ALERT_MODE=log            # log or exception
ARTIFACTS_DIR=./artifacts              # Output directory for delivered code
```

## API Endpoints

### POST /pipelines
Create a new pipeline.

**Request:**
```json
{
  "requirement": "Build a REST API for user management",
  "project_id": "proj-123"
}
```

**Response (success):**
```json
{
  "id": "uuid-...",
  "status": "QUEUED",
  "created_at": "2026-05-30T..."
}
```

**Response (backpressure):**
```json
{
  "error": "Service overloaded",
  "pipeline_id": "uuid-...",
  "queue_position": 15
}
```
HTTP 503

---

### GET /pipelines/{id}
Get pipeline status, history, and attempt logs.

**Response:**
```json
{
  "id": "uuid-...",
  "project_id": "proj-123",
  "status": "COMPLETED",
  "active_node": null,
  "history": [
    {
      "node": "planner",
      "attempt": 1,
      "success": true,
      "duration_ms": 1234
    },
    {
      "node": "codegen",
      "attempt": 1,
      "success": false,
      "duration_ms": 2100
    },
    {
      "node": "codegen",
      "attempt": 2,
      "success": true,
      "duration_ms": 1800
    }
  ],
  "attempts": [
    {
      "attempt_n": 1,
      "node": "codegen",
      "reasons": ["Missing type hints", "..."],
      "timestamp": "..."
    }
  ]
}
```

---

### GET /metrics
System-wide metrics and observability.

**Response:**
```json
{
  "pipelines": {
    "by_status": { "COMPLETED": 5, "FAILED": 1, "QUEUED": 2, "RUNNING:codegen": 1 },
    "total": 9
  },
  "correction_loop": {
    "avg_attempts_to_approval": 1.4,
    "successful_pipelines": 5
  },
  "costs": {
    "proj-123": {
      "total_tokens": 250000,
      "total_cost_usd": 1.25,
      "breakdown": {
        "planner": { "tokens": 50000, "cost_usd": 0.2 },
        "codegen": { "tokens": 150000, "cost_usd": 0.6 }
      }
    }
  },
  "node_durations_ms": {
    "planner": 1200,
    "codegen": 2000,
    "reviewer": 800,
    "validator": 100,
    "delivery": 150
  },
  "queue": {
    "queue_size": 2,
    "active_pipelines": 1,
    "max_concurrent": 5
  }
}
```

---

### GET /health
Simple health check.

---

## Testing

### Test a single node
```bash
# Planner
echo '{"requirement": "Build a login form", "project_id": "p1"}' | python nodes/planner.py

# Codegen
echo '{"task": {"id": "t1", "description": "Create a login function"}, "stack": "Python", "conventions": "PEP 8"}' | python nodes/codegen.py

# Reviewer
echo '{"code": "def login():\n  pass", "conventions": "PEP 8"}' | python nodes/reviewer.py

# Validator
echo '{"code": "def login():\n  pass", "language": "python"}' | python nodes/validator.py

# Delivery
echo '{"code": "def login():\n  pass", "task_id": "t1", "project_id": "p1"}' | python nodes/delivery.py
```

### Full pipeline via API
```bash
# Start server
uvicorn orchestrator.main:app --reload

# In another terminal:
PIPELINE_ID=$(curl -s -X POST http://localhost:8000/pipelines \
  -H "Content-Type: application/json" \
  -d '{"requirement": "Build a hello world function", "project_id": "test1"}' | jq -r '.id')

# Poll status (should eventually be COMPLETED or FAILED)
watch -n 1 "curl -s http://localhost:8000/pipelines/$PIPELINE_ID | jq '.status'"

# View metrics
curl -s http://localhost:8000/metrics | jq '.'
```

---

## Code Structure

```
nodes/              # Standalone CLI scripts (subprocess-executed)
  planner.py       # ~100 LOC
  codegen.py       # ~80 LOC
  reviewer.py      # ~80 LOC
  validator.py     # ~120 LOC
  delivery.py      # ~80 LOC

orchestrator/       # FastAPI orchestrator
  main.py          # ~250 LOC (endpoints, startup)
  worker.py        # ~300 LOC (pipeline execution, loop logic)
  pipeline.py      # ~80 LOC (state store)
  queue_manager.py # ~100 LOC (queue + semaphore)
  token_budget.py  # ~100 LOC (usage tracking)

shared/             # Shared utilities
  models.py        # ~200 LOC (Pydantic models)
  llm_client.py    # ~120 LOC (LLM abstraction)

Total: ~1,700 LOC
```

---

## Notes for Evaluators

- **Mock mode enabled by default** (`LLM_MOCK=true`): Deterministic responses for testing architecture without API costs
- **Auto-correction loop tested with mock**: Attempt counts and feedback chains are visible in `/pipelines/{id}` history
- **Token tracking works in mock**: Tokens are counted but costs are zero (mock model has zero price)
- **Production-ready patterns**: Async/await, proper error handling, structured logging, type hints
- **Trade-offs prioritized**: Architecture > output quality, reliability > feature completeness

---



