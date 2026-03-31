"""Codex provider."""

import shutil
from pathlib import Path

from quill.providers.base import AICLIProvider


class CodexProvider(AICLIProvider):
    name = "codex"

    def is_available(self) -> bool:
        return shutil.which("codex") is not None

    def build_command(
        self,
        mcp_server_cmd: str,
        session_dir: Path,
        extra_args: list[str],
    ) -> list[str]:
        parts = mcp_server_cmd.split()
        return [
            "codex",
            "-c",
            f"mcp quill {' '.join(parts)}",
            *extra_args,
        ]
