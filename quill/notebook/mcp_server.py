"""MCP server exposing marimo notebook tools to AI agents."""

from __future__ import annotations

import atexit
from pathlib import Path

from fastmcp import FastMCP

from quill.notebook.kernel import KernelSession
from quill.notebook.marimo_writer import MarimoNotebook

mcp = FastMCP("quill")

# ---------------------------------------------------------------------------
# Session state (one active session at a time)
# ---------------------------------------------------------------------------

_session: dict = {
    "kernel": None,
    "notebook": None,
    "notebook_path": None,
}


def _kernel() -> KernelSession:
    k = _session["kernel"]
    if k is None or not k.is_running:
        raise RuntimeError(
            "No active session. Call start_new_session or resume_session first."
        )
    return k


def _notebook() -> MarimoNotebook:
    nb = _session["notebook"]
    if nb is None:
        raise RuntimeError("No active session.")
    return nb


def _save() -> None:
    nb = _session["notebook"]
    path = _session["notebook_path"]
    if nb and path:
        nb.save(path)


def _format(output) -> str:  # noqa: ANN001
    return output.to_text()


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def start_new_session(
    notebook_path: str,
    session_name: str = "",
) -> str:
    """Start a new marimo notebook session.

    Creates a new marimo .py notebook file and starts a Python kernel.

    Args:
        notebook_path: Path where the notebook (.py) will be saved.
        session_name: Optional title for the notebook.
    """
    if _session["kernel"] and _session["kernel"].is_running:
        _session["kernel"].shutdown()

    path = Path(notebook_path).resolve()
    if not path.suffix:
        path = path.with_suffix(".py")

    notebook = MarimoNotebook(app_title=session_name or None)
    kernel = KernelSession()
    kernel.start()

    _session["kernel"] = kernel
    _session["notebook"] = notebook
    _session["notebook_path"] = str(path)

    notebook.save(path)
    return f"Session started. Notebook: {path}"


@mcp.tool()
async def resume_session(notebook_path: str) -> str:
    """Resume an existing marimo notebook session.

    Loads an existing marimo .py notebook, starts a kernel, and re-executes
    all code cells to restore state.

    Args:
        notebook_path: Path to the existing notebook (.py).
    """
    path = Path(notebook_path).resolve()
    if not path.exists():
        return f"Error: Notebook not found at {path}"

    if _session["kernel"] and _session["kernel"].is_running:
        _session["kernel"].shutdown()

    notebook = MarimoNotebook.from_file(path)
    kernel = KernelSession()
    kernel.start()

    for cell in notebook.cells:
        if not cell.is_markdown:
            kernel.execute(cell.code)

    _session["kernel"] = kernel
    _session["notebook"] = notebook
    _session["notebook_path"] = str(path)

    n = len(notebook.cells)
    return f"Session resumed. Notebook: {path} ({n} cells loaded and executed)"


@mcp.tool()
async def continue_session(
    source_notebook_path: str,
    new_notebook_path: str,
) -> str:
    """Fork an existing notebook into a new session.

    Copies cells from an existing notebook into a new file and starts a kernel.

    Args:
        source_notebook_path: Path to the source notebook.
        new_notebook_path: Path for the new notebook file.
    """
    source = Path(source_notebook_path).resolve()
    if not source.exists():
        return f"Error: Source notebook not found at {source}"

    if _session["kernel"] and _session["kernel"].is_running:
        _session["kernel"].shutdown()

    notebook = MarimoNotebook.from_file(source)
    new_path = Path(new_notebook_path).resolve()
    if not new_path.suffix:
        new_path = new_path.with_suffix(".py")

    kernel = KernelSession()
    kernel.start()

    for cell in notebook.cells:
        if not cell.is_markdown:
            kernel.execute(cell.code)

    _session["kernel"] = kernel
    _session["notebook"] = notebook
    _session["notebook_path"] = str(new_path)
    notebook.save(new_path)

    n = len(notebook.cells)
    return f"Session forked. Notebook: {new_path} ({n} cells carried over)"


@mcp.tool()
async def execute_code(code: str, cell_name: str = "") -> str:
    """Execute Python code and add it as a new cell in the notebook.

    Runs the code in the kernel and appends it as a new marimo cell.
    Returns stdout, the result of the last expression, or any errors.

    Args:
        code: Python code to execute.
        cell_name: Optional name for the cell.
    """
    kernel = _kernel()
    notebook = _notebook()

    output = await kernel.execute_async(code)
    notebook.add_cell(code=code, name=cell_name or None)
    _save()

    idx = len(notebook.cells) - 1
    return f"[Cell {idx}]\n{_format(output)}"


@mcp.tool()
async def add_markdown(text: str, cell_name: str = "") -> str:
    """Add a markdown documentation cell to the notebook.

    The text is wrapped in marimo's mo.md() for rendering.

    Args:
        text: Markdown content.
        cell_name: Optional name for the cell.
    """
    notebook = _notebook()
    notebook.add_cell(code=text, name=cell_name or None, is_markdown=True)
    _save()

    idx = len(notebook.cells) - 1
    return f"Markdown cell added at index {idx}."


@mcp.tool()
async def edit_cell(cell_index: int, new_code: str) -> str:
    """Edit an existing cell and re-execute it.

    Replaces the code of an existing cell and re-runs it in the kernel.

    Args:
        cell_index: 0-based index of the cell to edit.
        new_code: Replacement code.
    """
    kernel = _kernel()
    notebook = _notebook()

    try:
        cell = notebook.edit_cell(cell_index, new_code)
    except IndexError as exc:
        return f"Error: {exc}"

    if cell.is_markdown:
        _save()
        return f"Markdown cell {cell_index} updated."

    output = await kernel.execute_async(new_code)
    _save()
    return f"[Cell {cell_index} updated]\n{_format(output)}"


@mcp.tool()
async def shutdown_session() -> str:
    """Save the notebook and shut down the kernel."""
    _save()
    path = _session["notebook_path"]

    if _session["kernel"]:
        _session["kernel"].shutdown()

    _session["kernel"] = None
    _session["notebook"] = None
    _session["notebook_path"] = None

    return f"Session shut down. Notebook saved to {path}"


# ---------------------------------------------------------------------------
# MCP resource
# ---------------------------------------------------------------------------


@mcp.resource("quill://server/status")
def server_status() -> str:
    """Current server status."""
    kernel = _session["kernel"]
    notebook = _session["notebook"]
    path = _session["notebook_path"]

    if kernel and kernel.is_running:
        n = len(notebook.cells) if notebook else 0
        return f"Active session: {path} ({n} cells)"
    return "No active session"


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def _cleanup() -> None:
    if _session["kernel"] and _session["kernel"].is_running:
        _save()
        _session["kernel"].shutdown()


atexit.register(_cleanup)


if __name__ == "__main__":
    mcp.run(transport="stdio")
