import os
import json
import platform
from .models import TokenUsage

# On Windows + Python 3.13, platform._wmi_query() (used by platform.win32_ver(),
# which the openai SDK calls to build its "X-Stainless-OS" header) can hang for
# seconds or block indefinitely. Neutralise it so platform falls back to its
# non-WMI code path, then prime the caches so no lookup happens mid-request.
if os.name == "nt":
    try:
        def _no_wmi(*_args, **_kwargs):
            raise OSError("WMI disabled (platform._wmi_query hangs on this Python build)")

        platform._wmi_query = _no_wmi  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        platform.uname()      # fills platform._uname_cache
        platform.platform()   # fills platform._platform_cache
    except Exception:
        pass
    # Belt-and-suspenders: tell the SDK not to probe the OS at all if it supports it.
    os.environ.setdefault("OPENAI_DISABLE_PLATFORM_HEADER", "1")

# Bedrock model used when LLM_PROVIDER=bedrock (override with BEDROCK_MODEL_ID)
DEFAULT_BEDROCK_MODEL_ID = "us.anthropic.claude-sonnet-4-6"

# Max output tokens per completion. 2048 truncates codegen output for anything
# non-trivial (e.g. a full HTML/JS game), which then fails review. Override with
# LLM_MAX_OUTPUT_TOKENS.
MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "8192"))


class LLMClient:
    def __init__(self):
        self.mock_mode = os.getenv("LLM_MOCK", "true").lower() == "true"
        self.provider = os.getenv("LLM_PROVIDER", "anthropic")
        self.bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_BEDROCK_MODEL_ID)
        # Azure OpenAI deployment name (used when LLM_PROVIDER=azure)
        self.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")

        if not self.mock_mode:
            if self.provider == "anthropic":
                from anthropic import Anthropic
                self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
            elif self.provider == "bedrock":
                from anthropic import AnthropicBedrock
                # Credentials & region are read from AWS_* env vars
                self.client = AnthropicBedrock(
                    aws_region=os.getenv("AWS_REGION")
                    or os.getenv("AWS_DEFAULT_REGION")
                    or "us-east-1"
                )
            elif self.provider == "azure":
                from openai import AzureOpenAI
                self.client = AzureOpenAI(
                    azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
                    api_key=os.getenv("OPENAI_KEY"),
                    api_version=os.getenv("OPENAI_VERSION", "2024-08-01-preview"),
                )
            elif self.provider == "openai":
                from openai import OpenAI
                self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def complete(self, prompt: str) -> tuple[str, TokenUsage]:
        """
        Call LLM and return (text, TokenUsage).
        In mock mode, returns deterministic responses.
        """
        if self.mock_mode:
            return self._mock_complete(prompt)

        if self.provider == "anthropic":
            return self._anthropic_complete(prompt)
        elif self.provider == "bedrock":
            return self._bedrock_complete(prompt)
        elif self.provider == "azure":
            return self._azure_complete(prompt)
        elif self.provider == "openai":
            return self._openai_complete(prompt)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _mock_complete(self, prompt: str) -> tuple[str, TokenUsage]:
        """Return deterministic mock responses based on prompt context."""
        # Mock responses for different node types
        if "task" in prompt.lower() and "break" in prompt.lower():
            # planner response
            response = json.dumps({
                "tasks": [
                    {"id": "task1", "description": "Setup environment", "priority": "high"},
                    {"id": "task2", "description": "Create API routes", "priority": "high"}
                ],
                "stack": "Python FastAPI",
                "conventions": "PEP 8, type hints, docstrings"
            })
        elif "code" in prompt.lower() and "generate" in prompt.lower():
            # codegen response
            response = """def hello_world():
    '''A simple hello world function.'''
    return "Hello, World!"
"""
        elif "review" in prompt.lower() or "check" in prompt.lower():
            # reviewer response
            response = json.dumps({
                "approved": True,
                "issues": [],
                "suggestions": ["Add type hints to function parameters"]
            })
        elif "validate" in prompt.lower() or "syntax" in prompt.lower():
            # validator response
            response = json.dumps({
                "passed": True,
                "errors": [],
                "warnings": []
            })
        else:
            response = "Task completed successfully."

        tokens = TokenUsage(
            input=len(prompt.split()),
            output=len(response.split()),
            model="mock-gpt-4"
        )
        return response, tokens

    def _anthropic_complete(self, prompt: str) -> tuple[str, TokenUsage]:
        """Call Anthropic API."""
        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text
        tokens = TokenUsage(
            input=message.usage.input_tokens,
            output=message.usage.output_tokens,
            model="claude-3-5-sonnet-20241022"
        )
        return text, tokens

    def _bedrock_complete(self, prompt: str) -> tuple[str, TokenUsage]:
        """Call Claude on Amazon Bedrock via the Anthropic Messages API."""
        message = self.client.messages.create(
            model=self.bedrock_model_id,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text
        tokens = TokenUsage(
            input=message.usage.input_tokens,
            output=message.usage.output_tokens,
            model=self.bedrock_model_id
        )
        return text, tokens

    def _azure_complete(self, prompt: str) -> tuple[str, TokenUsage]:
        """Call Azure OpenAI (model = Azure deployment name)."""
        response = self.client.chat.completions.create(
            model=self.azure_deployment,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=MAX_OUTPUT_TOKENS,
        )
        choice = response.choices[0]
        text = choice.message.content
        if choice.finish_reason == "length":
            raise RuntimeError(
                f"Azure response truncated at {MAX_OUTPUT_TOKENS} output tokens "
                "(finish_reason=length); raise LLM_MAX_OUTPUT_TOKENS."
            )
        tokens = TokenUsage(
            input=response.usage.prompt_tokens,
            output=response.usage.completion_tokens,
            model=self.azure_deployment,
        )
        return text, tokens

    def _openai_complete(self, prompt: str) -> tuple[str, TokenUsage]:
        """Call OpenAI API."""
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=MAX_OUTPUT_TOKENS
        )
        text = response.choices[0].message.content
        tokens = TokenUsage(
            input=response.usage.prompt_tokens,
            output=response.usage.completion_tokens,
            model="gpt-4o-mini"
        )
        return text, tokens
