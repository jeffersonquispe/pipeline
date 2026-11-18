import logging
import os
from typing import Dict, List
from shared import TokenUsage, BudgetReport

logger = logging.getLogger(__name__)


class TokenBudgetManager:
    """Manage token usage and costs across projects and nodes."""

    PRICES = {
        "claude-3-5-sonnet-20241022": {"input": 0.80, "output": 4.00},  # USD per 1M tokens
        "claude-3-5-haiku": {"input": 0.80, "output": 4.00},
        # AWS Bedrock (LLM_PROVIDER=bedrock)
        "us.anthropic.claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
        "us.anthropic.claude-3-5-sonnet-20241022-v2:0": {"input": 3.00, "output": 15.00},
        "us.anthropic.claude-3-5-haiku-20241022-v1:0": {"input": 0.80, "output": 4.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        # Azure OpenAI deployment (LLM_PROVIDER=azure)
        "asistentelupita-llm-work-agent-gpt52": {"input": 1.25, "output": 10.00},
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "mock-gpt-4": {"input": 0.0, "output": 0.0},  # Free for mocks
    }

    def __init__(self):
        self.budget_alert_usd = float(os.getenv("TOKEN_BUDGET_ALERT_USD", "10.0"))
        self.alert_mode = os.getenv("TOKEN_BUDGET_ALERT_MODE", "log")  # log or exception
        self.usage: Dict[str, Dict[str, List[TokenUsage]]] = {}

    def record(self, project_id: str, node: str, token_usage: TokenUsage) -> None:
        """Record token usage for a project and node."""
        if project_id not in self.usage:
            self.usage[project_id] = {}
        if node not in self.usage[project_id]:
            self.usage[project_id][node] = []

        self.usage[project_id][node].append(token_usage)
        logger.info(f"Recorded {token_usage.model} usage for {project_id}/{node}")

        # Check budget
        self.check_budget(project_id)

    def get_cost(self, token_usage: TokenUsage) -> float:
        """Calculate cost in USD for token usage."""
        prices = self.PRICES.get(token_usage.model, {"input": 0.0, "output": 0.0})
        input_cost = (token_usage.input / 1_000_000) * prices["input"]
        output_cost = (token_usage.output / 1_000_000) * prices["output"]
        return input_cost + output_cost

    def get_report(self, project_id: str) -> BudgetReport:
        """Get usage report for a project."""
        if project_id not in self.usage:
            return BudgetReport(
                project_id=project_id,
                total_tokens=0,
                total_cost_usd=0.0,
                breakdown={}
            )

        total_tokens = 0
        total_cost_usd = 0.0
        breakdown = {}

        for node, token_list in self.usage[project_id].items():
            node_tokens = sum(t.input + t.output for t in token_list)
            node_cost = sum(self.get_cost(t) for t in token_list)

            breakdown[node] = {
                "tokens": node_tokens,
                "cost_usd": round(node_cost, 4),
                "calls": len(token_list)
            }

            total_tokens += node_tokens
            total_cost_usd += node_cost

        return BudgetReport(
            project_id=project_id,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost_usd, 4),
            breakdown=breakdown
        )

    def check_budget(self, project_id: str) -> None:
        """Check if project exceeds budget threshold."""
        report = self.get_report(project_id)

        if report.total_cost_usd > self.budget_alert_usd:
            message = (
                f"Project {project_id} exceeded budget threshold: "
                f"${report.total_cost_usd:.4f} > ${self.budget_alert_usd:.4f}"
            )

            if self.alert_mode == "exception":
                raise BudgetExceededError(message)
            else:
                logger.warning(message)

    def reset_project(self, project_id: str) -> None:
        """Reset usage tracking for a project."""
        if project_id in self.usage:
            del self.usage[project_id]
            logger.info(f"Reset usage tracking for project {project_id}")


class BudgetExceededError(Exception):
    """Raised when project budget is exceeded."""
    pass
