"""Claude Code provider."""

import json
import shutil
from pathlib import Path

from quill.providers.base import AICLIProvider


CLAUDE_COPILOT_SETTINGS = {
    "permissions": {
        "allow": [
            "mcp__quill__start_new_session",
            "mcp__quill__resume_session",
            "mcp__quill__continue_session",
            "mcp__quill__execute_code",
            "mcp__quill__add_markdown",
            "mcp__quill__edit_cell",
            "mcp__quill__shutdown_session",
        ]
    }
}


class ClaudeProvider(AICLIProvider):
    name = "claude"

    def is_available(self) -> bool:
        return shutil.which("claude") is not None

    def build_command(
        self,
        mcp_server_cmd: str,
        session_dir: Path,
        extra_args: list[str],
    ) -> list[str]:
        parts = mcp_server_cmd.split()

        mcp_config = {
            "mcpServers": {
                "quill": {
                    "command": parts[0],
                    "args": parts[1:],
                }
            }
        }

        mcp_config_path = session_dir / "mcp_config.json"
        mcp_config_path.write_text(json.dumps(mcp_config, indent=2))

        settings_path = session_dir / "settings.json"
        settings_path.write_text(json.dumps(CLAUDE_COPILOT_SETTINGS, indent=2))

        return [
            "claude",
            "--mcp-config",
            str(mcp_config_path),
            "--settings",
            str(settings_path),
            *extra_args,
        ]
