"""Provider registry and utilities."""

from quill.providers.base import AICLIProvider
from quill.providers.claude import ClaudeProvider
from quill.providers.codex import CodexProvider
from quill.providers.gemini import GeminiProvider

_PROVIDERS: dict[str, type[AICLIProvider]] = {
    "claude": ClaudeProvider,
    "codex": CodexProvider,
    "gemini": GeminiProvider,
}


def get_provider(name: str) -> AICLIProvider:
    """Get a provider instance by name."""
    if name not in _PROVIDERS:
        available = ", ".join(_PROVIDERS)
        raise ValueError(f"Unknown provider: {name}. Available: {available}")
    return _PROVIDERS[name]()
