"""Shared helper for Anthropic structured-output calls."""

from dataclasses import dataclass, field
from typing import TypeVar

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from pubmed_extraction.settings import settings

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    pass


@dataclass
class UsageTracker:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: list[str] = field(default_factory=list)


def get_client() -> Anthropic:
    if not settings.anthropic_api_key:
        raise LLMError("PX_ANTHROPIC_API_KEY is not set; required for LLM calls.")
    return Anthropic(api_key=settings.anthropic_api_key)


def structured_call(
    client: Anthropic,
    *,
    model: str,
    max_tokens: int,
    system: str,
    user_content: str,
    output_model: type[T],
    usage: UsageTracker,
    effort: str | None = None,
    timeout: float | None = None,
) -> T:
    """Run a structured-output request and return the parsed Pydantic object.

    effort: None sends no thinking configuration (model default); "disabled" turns
    thinking off; any other value is sent as output_config.effort.
    """
    extra: dict = {}
    if effort == "disabled":
        extra["thinking"] = {"type": "disabled"}
    elif effort:
        extra["output_config"] = {"effort": effort}

    api = client.with_options(timeout=timeout) if timeout else client
    try:
        response = api.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_content}],
            output_format=output_model,
            **extra,
        )
    except ValidationError as exc:
        raise LLMError(
            f"{output_model.__name__}: invalid output (often truncated by max_tokens, "
            f"thinking included): {exc}"
        ) from exc

    usage.input_tokens += response.usage.input_tokens
    usage.output_tokens += response.usage.output_tokens
    usage.calls.append(output_model.__name__)

    if response.stop_reason in ("refusal", "max_tokens"):
        raise LLMError(f"{output_model.__name__}: stop_reason={response.stop_reason}")
    if response.parsed_output is None:
        raise LLMError(f"{output_model.__name__}: empty parsed output")
    return response.parsed_output
