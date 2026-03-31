"""Command implementations."""

import subprocess
import sys
from pathlib import Path

from quill.cli._cli_utils import get_python_path
from quill.providers._provider_utils import get_provider

QUILL_DIR = Path.home() / ".quill" / "sessions"


def copilot_impl(provider_name: str, extra_args: list[str]) -> None:
    """Launch an AI agent with the Quill MCP server."""
    provider = get_provider(provider_name)

    if not provider.is_available():
        print(f"Error: {provider_name} CLI is not installed or not available.")
        sys.exit(1)

    python_path = get_python_path()
    mcp_server_cmd = f"{python_path} -m quill.notebook.mcp_server"

    QUILL_DIR.mkdir(parents=True, exist_ok=True)

    cmd = provider.build_command(mcp_server_cmd, QUILL_DIR, extra_args)

    try:
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        pass
