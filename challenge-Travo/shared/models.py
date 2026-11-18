from pydantic import BaseModel, Field
from typing import Optional, List, Any, Dict
from datetime import datetime


class TokenUsage(BaseModel):
    input: int
    output: int
    model: str


class PlannerInput(BaseModel):
    requirement: str
    project_id: str


class Task(BaseModel):
    id: str
    description: str
    priority: str = "medium"


class PlannerOutput(BaseModel):
    tasks: List[Task]
    stack: str
    conventions: str
    tokens: Optional[TokenUsage] = None


class CodegenInput(BaseModel):
    task: Task
    stack: str
    conventions: str
    feedback: Optional[List[str]] = None


class CodegenOutput(BaseModel):
    code: str
    language: str
    task_id: str
    tokens: TokenUsage


class ReviewerInput(BaseModel):
    code: str
    conventions: str


class ReviewerOutput(BaseModel):
    approved: bool
    issues: List[str]
    suggestions: List[str]
    tokens: TokenUsage


class ValidatorInput(BaseModel):
    code: str
    language: str


class ValidatorOutput(BaseModel):
    passed: bool
    errors: List[str]
    warnings: List[str]
    tokens: Optional[TokenUsage] = None


class DeliveryInput(BaseModel):
    code: str
    task_id: str
    project_id: str


class DeliveryOutput(BaseModel):
    status: str
    artifact_path: str


class PipelineAttempt(BaseModel):
    attempt_n: int
    node: str
    reasons: List[str]
    feedback: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0


class PipelineHistory(BaseModel):
    node: str
    attempt: int
    input: Dict[str, Any]
    output: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    duration_ms: int = 0
    success: bool


class Pipeline(BaseModel):
    id: str
    project_id: str
    requirement: str
    status: str = "QUEUED"
    active_node: Optional[str] = None
    history: List[PipelineHistory] = Field(default_factory=list)
    attempts: List[PipelineAttempt] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None


class BudgetReport(BaseModel):
    project_id: str
    total_tokens: int
    total_cost_usd: float
    breakdown: Dict[str, Dict[str, Any]]  # {node: {tokens, cost}}
