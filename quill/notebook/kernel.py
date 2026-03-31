"""Lightweight Python execution session using a subprocess.

No Jupyter/IPython dependency — just a persistent Python process that
communicates via stdin/stdout with a thin JSON protocol.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field


# The helper script is sent to the subprocess on startup.  It sits in a
# read-eval-print loop, executing code received as JSON lines and
# replying with JSON results (stdout, the repr of the last expression,
# traceback, and base64-encoded images captured from matplotlib).
_RUNNER = textwrap.dedent(r'''
import ast, base64, io, json, sys, traceback

_globals = {"__name__": "__main__", "__builtins__": __builtins__}

# Matplotlib image capture hook
_images: list[str] = []

def _install_mpl_hook():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as _plt

        _orig_show = _plt.show

        def _capture_show(*a, **kw):
            buf = io.BytesIO()
            for fig_num in _plt.get_fignums():
                fig = _plt.figure(fig_num)
                fig.savefig(buf, format="png", bbox_inches="tight")
                _images.append(base64.b64encode(buf.getvalue()).decode())
                buf.seek(0)
                buf.truncate()
            _plt.close("all")

        _plt.show = _capture_show
    except ImportError:
        pass

_install_mpl_hook()

while True:
    try:
        line = sys.stdin.readline()
        if not line:
            break
        request = json.loads(line)
        code = request["code"]
    except Exception:
        break

    stdout_capture = io.StringIO()
    result_repr = None
    error_tb = None
    _images.clear()

    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = stdout_capture
    sys.stderr = stdout_capture

    try:
        tree = ast.parse(code)
        # If the last statement is an expression, capture its value
        last_expr = None
        if tree.body and isinstance(tree.body[-1], ast.Expr):
            last_expr = ast.Expression(tree.body.pop().value)
            ast.fix_missing_locations(last_expr)

        compiled = compile(tree, "<cell>", "exec")
        exec(compiled, _globals)

        if last_expr is not None:
            compiled_expr = compile(last_expr, "<cell>", "eval")
            value = eval(compiled_expr, _globals)
            if value is not None:
                result_repr = repr(value)
    except Exception:
        error_tb = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    response = {
        "stdout": stdout_capture.getvalue(),
        "result": result_repr,
        "error": error_tb,
        "images": list(_images),
    }
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()
''')


@dataclass
class CellOutput:
    """Represents the output of executing a cell."""

    text_outputs: list[str] = field(default_factory=list)
    error: str | None = None
    result: str | None = None
    images: list[bytes] = field(default_factory=list)

    def to_text(self) -> str:
        """Format output as a human-readable string."""
        parts = []
        if self.text_outputs:
            text = "".join(self.text_outputs)
            if text:
                parts.append(text)
        if self.result:
            parts.append(self.result)
        if self.error:
            parts.append(f"Error:\n{self.error}")
        if self.images:
            parts.append(f"[{len(self.images)} image(s) generated]")
        return "\n".join(parts) if parts else "(no output)"


class KernelSession:
    """Manages a persistent Python subprocess for code execution."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None

    @property
    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def start(self) -> None:
        """Start the Python subprocess."""
        self._proc = subprocess.Popen(
            [sys.executable, "-c", _RUNNER],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def shutdown(self) -> None:
        """Terminate the subprocess."""
        if self._proc:
            self._proc.stdin.close()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait()
            self._proc = None

    def execute(self, code: str, timeout: int = 120) -> CellOutput:
        """Execute code and return captured output."""
        if not self.is_running:
            raise RuntimeError("Kernel is not running")

        output = CellOutput()
        request = json.dumps({"code": code}) + "\n"

        try:
            self._proc.stdin.write(request)
            self._proc.stdin.flush()
            response_line = self._proc.stdout.readline()
            if not response_line:
                output.error = "Kernel process terminated unexpectedly."
                return output
            response = json.loads(response_line)
        except Exception as exc:
            output.error = f"Kernel communication error: {exc}"
            return output

        if response.get("stdout"):
            output.text_outputs.append(response["stdout"])
        output.result = response.get("result")
        output.error = response.get("error")

        import base64

        for img_b64 in response.get("images", []):
            output.images.append(base64.b64decode(img_b64))

        return output

    async def execute_async(self, code: str, timeout: int = 120) -> CellOutput:
        """Async wrapper around execute."""
        return await asyncio.to_thread(self.execute, code, timeout)
