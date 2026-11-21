"""Small provider adapter interface for OpenAI and Anthropic chat APIs."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Generation:
    text: str
    input_tokens: int
    output_tokens: int


class LLMProvider(Protocol):
    """Provider interface; implementations return JSON text and token usage."""

    model: str
    provider_name: str

    def generate(self, prompt: str) -> Generation: ...


class OpenAIProvider:
    def __init__(self, model: str, api_key: str, base_url: str | None = None) -> None:
        from openai import OpenAI

        self.model = model
        self.provider_name = "openai"
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def generate(self, prompt: str) -> Generation:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("OpenAI returned an empty response")
        usage = response.usage
        return Generation(
            content, usage.prompt_tokens if usage else 0, usage.completion_tokens if usage else 0
        )


class AnthropicProvider:
    def __init__(self, model: str, api_key: str) -> None:
        from anthropic import Anthropic

        self.model = model
        self.provider_name = "anthropic"
        self.client = Anthropic(api_key=api_key)

    def generate(self, prompt: str) -> Generation:
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system="Return only a valid JSON object matching the requested schema.",
            messages=[{"role": "user", "content": prompt}],
        )
        content = "\n".join(block.text for block in response.content if block.type == "text")
        if not content:
            raise ValueError("Anthropic returned an empty response")
        return Generation(content, response.usage.input_tokens, response.usage.output_tokens)


def create_provider(
    provider: str,
    model: str,
    openai_key: str | None,
    anthropic_key: str | None,
    openai_base_url: str | None = None,
) -> LLMProvider:
    """Build the configured provider; credentials are never logged."""
    normalized = provider.casefold()
    if normalized == "openai":
        if not openai_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return OpenAIProvider(model, openai_key, base_url=openai_base_url)
    if normalized == "anthropic":
        if not anthropic_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return AnthropicProvider(model, anthropic_key)
    raise ValueError(f"Unsupported LLM_PROVIDER {provider!r}; choose openai or anthropic")
