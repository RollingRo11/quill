"""Gemini CLI provider."""

import json
import shutil
from pathlib import Path

from quill.providers.base import AICLIProvider


class GeminiProvider(AICLIProvider):
    name = "gemini"

    def is_available(self) -> bool:
        return shutil.which("gemini") is not None

    def build_command(
        self,
        mcp_server_cmd: str,
        session_dir: Path,
        extra_args: list[str],
    ) -> list[str]:
        parts = mcp_server_cmd.split()

        gemini_dir = Path.cwd() / ".gemini"
        gemini_dir.mkdir(exist_ok=True)

        settings_path = gemini_dir / "settings.json"

        settings: dict = {}
        if settings_path.exists():
            try:
                settings = json.loads(settings_path.read_text())
            except json.JSONDecodeError:
                pass

        settings.setdefault("mcpServers", {})
        settings["mcpServers"]["quill"] = {
            "command": parts[0],
            "args": parts[1:],
        }

        settings_path.write_text(json.dumps(settings, indent=2))

        return ["gemini", *extra_args]
