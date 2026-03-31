"""Base provider class for AI CLI agents."""

from abc import ABC, abstractmethod
from pathlib import Path


class AICLIProvider(ABC):
    """Abstract base class for AI CLI providers."""

    name: str

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider CLI is installed and available."""
        ...

    @abstractmethod
    def build_command(
        self,
        mcp_server_cmd: str,
        session_dir: Path,
        extra_args: list[str],
    ) -> list[str]:
        """Build the command to launch the agent with MCP config."""
        ...
