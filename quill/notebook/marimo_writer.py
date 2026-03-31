"""Generates and parses marimo .py notebook files."""

from __future__ import annotations

import ast
import builtins
import re
from dataclasses import dataclass, field
from pathlib import Path

BUILTINS = set(dir(builtins))


@dataclass
class Cell:
    """A single cell in a marimo notebook."""

    name: str
    code: str
    is_markdown: bool = False
    config: dict = field(default_factory=dict)


@dataclass
class MarimoNotebook:
    """In-memory representation of a marimo notebook."""

    cells: list[Cell] = field(default_factory=list)
    app_title: str | None = None
    app_width: str = "medium"

    def add_cell(
        self,
        code: str,
        name: str | None = None,
        is_markdown: bool = False,
    ) -> Cell:
        """Add a new cell to the notebook."""
        cell = Cell(name=name or "_", code=code, is_markdown=is_markdown)
        self.cells.append(cell)
        return cell

    def edit_cell(self, index: int, new_code: str) -> Cell:
        """Replace the code of an existing cell."""
        if index < 0 or index >= len(self.cells):
            raise IndexError(
                f"Cell index {index} out of range (0-{len(self.cells) - 1})"
            )
        self.cells[index].code = new_code
        return self.cells[index]

    def to_python(self) -> str:
        """Generate the marimo .py notebook file contents."""
        cells = list(self.cells)

        # Auto-insert `import marimo as mo` if any cell needs it
        needs_mo = any(
            c.is_markdown or "mo." in c.code or "mo " in c.code for c in cells
        )
        has_mo = any("import marimo as mo" in c.code for c in cells)
        if needs_mo and not has_mo:
            cells.insert(0, Cell(name="_", code="import marimo as mo"))

        # Analyse every cell for defs / refs
        cell_defs: list[set[str]] = []
        cell_refs: list[set[str]] = []
        for cell in cells:
            if cell.is_markdown:
                cell_defs.append(set())
                cell_refs.append({"mo"})
            else:
                defs, refs = _analyze_cell(cell.code)
                cell_defs.append(defs)
                cell_refs.append(refs)

        # Global map: variable name -> index of defining cell
        all_defs: dict[str, int] = {}
        for i, defs in enumerate(cell_defs):
            for name in defs:
                all_defs[name] = i

        lines: list[str] = []
        lines.append("import marimo")
        lines.append("")
        lines.append('__generated_with = "0.1.0"')

        # App instantiation
        app_kwargs: list[str] = []
        if self.app_title:
            app_kwargs.append(f"app_title={self.app_title!r}")
        if self.app_width != "medium":
            app_kwargs.append(f"width={self.app_width!r}")

        if app_kwargs:
            lines.append(f"app = marimo.App({', '.join(app_kwargs)})")
        else:
            lines.append("app = marimo.App()")

        used_names: dict[str, int] = {}

        for i, cell in enumerate(cells):
            lines.append("")
            lines.append("")

            # Decorator (with optional config)
            if cell.config:
                cfg = ", ".join(f"{k}={v!r}" for k, v in cell.config.items())
                lines.append(f"@app.cell({cfg})")
            else:
                lines.append("@app.cell")

            # Compute inputs
            refs = cell_refs[i]
            defs = cell_defs[i]
            inputs = sorted(
                name
                for name in refs
                if name not in defs
                and name not in BUILTINS
                and name != "_"
                and name in all_defs
                and all_defs[name] != i
            )

            # Compute outputs
            outputs = sorted(name for name in defs if not name.startswith("_"))

            # Deduplicate function names (skip for unnamed cells)
            func_name = cell.name
            if func_name != "_":
                if func_name in used_names:
                    used_names[func_name] += 1
                    func_name = f"{func_name}_{used_names[func_name]}"
                else:
                    used_names[func_name] = 0

            params = ", ".join(inputs)
            lines.append(f"def {func_name}({params}):")

            # Cell body
            if cell.is_markdown:
                code = f'mo.md(r"""\n{cell.code}\n""")'
            else:
                code = cell.code

            for code_line in code.split("\n"):
                lines.append(f"    {code_line}")

            # Return statement
            if outputs:
                ret = ", ".join(outputs)
                lines.append(f"    return ({ret},)")
            else:
                lines.append("    return")

        lines.append("")
        lines.append("")
        lines.append('if __name__ == "__main__":')
        lines.append("    app.run()")
        lines.append("")
        return "\n".join(lines)

    def save(self, path: str | Path) -> None:
        """Write the notebook to a .py file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_python())

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @classmethod
    def from_file(cls, path: str | Path) -> MarimoNotebook:
        """Parse an existing marimo .py notebook."""
        return cls.from_source(Path(path).read_text())

    @classmethod
    def from_source(cls, source: str) -> MarimoNotebook:
        """Parse a marimo notebook from source code."""
        notebook = cls()

        # Parse app config
        app_match = re.search(
            r"app\s*=\s*marimo\.App\((.*?)\)", source, re.DOTALL
        )
        if app_match:
            kwargs_str = app_match.group(1).strip()
            if kwargs_str:
                for m in re.finditer(r'(\w+)\s*=\s*["\']([^"\']*)["\']', kwargs_str):
                    key, value = m.groups()
                    if key == "app_title":
                        notebook.app_title = value
                    elif key == "width":
                        notebook.app_width = value

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return notebook

        source_lines = source.split("\n")

        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if not _is_app_cell(node):
                continue

            # Extract body statements, stripping the return
            body_stmts = list(node.body)
            if body_stmts and isinstance(body_stmts[-1], ast.Return):
                body_stmts = body_stmts[:-1]

            if not body_stmts:
                code = ""
            else:
                start = body_stmts[0].lineno - 1
                end = body_stmts[-1].end_lineno  # type: ignore[union-attr]
                body_lines = source_lines[start:end]

                # Dedent
                min_indent = float("inf")
                for line in body_lines:
                    if line.strip():
                        min_indent = min(min_indent, len(line) - len(line.lstrip()))
                if min_indent == float("inf"):
                    min_indent = 0
                indent = int(min_indent)
                body_lines = [
                    line[indent:] if len(line) >= indent else line
                    for line in body_lines
                ]
                code = "\n".join(body_lines).rstrip()

            # Detect markdown cells
            is_markdown = False
            if "mo.md(" in code:
                is_markdown = True
                md_match = re.search(
                    r'mo\.md\(\s*(?:r|f|rf|fr)?\s*"""(.*?)"""\s*\)',
                    code,
                    re.DOTALL,
                )
                if md_match:
                    code = md_match.group(1).strip()

            notebook.cells.append(
                Cell(name=node.name, code=code, is_markdown=is_markdown)
            )

        return notebook


# ------------------------------------------------------------------
# AST analysis helpers
# ------------------------------------------------------------------


def _is_app_cell(node: ast.FunctionDef) -> bool:
    """Check if a function is decorated with @app.cell."""
    for dec in node.decorator_list:
        if isinstance(dec, ast.Attribute):
            if (
                isinstance(dec.value, ast.Name)
                and dec.value.id == "app"
                and dec.attr == "cell"
            ):
                return True
        elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
            if (
                isinstance(dec.func.value, ast.Name)
                and dec.func.value.id == "app"
                and dec.func.attr == "cell"
            ):
                return True
    return False


def _analyze_cell(code: str) -> tuple[set[str], set[str]]:
    """Return (defined_names, referenced_names) for a cell."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set(), set()

    analyzer = _CellAnalyzer()
    analyzer.visit(tree)
    return analyzer.defs, analyzer.refs


class _CellAnalyzer(ast.NodeVisitor):
    """Extract top-level definitions and all name references from a cell."""

    def __init__(self) -> None:
        self.defs: set[str] = set()
        self.refs: set[str] = set()
        self._scope_depth = 0

    # --- names -----------------------------------------------------------

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            if self._scope_depth == 0:
                self.defs.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.refs.add(node.id)
        self.generic_visit(node)

    # --- imports ---------------------------------------------------------

    def visit_Import(self, node: ast.Import) -> None:
        if self._scope_depth == 0:
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name.split(".")[0]
                self.defs.add(name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._scope_depth == 0:
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                if name != "*":
                    self.defs.add(name)

    # --- augmented assignment (reads + writes) ---------------------------

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        if isinstance(node.target, ast.Name):
            if self._scope_depth == 0:
                self.defs.add(node.target.id)
            self.refs.add(node.target.id)
        else:
            self.visit(node.target)
        self.visit(node.value)

    # --- scoped constructs -----------------------------------------------

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._scope_depth == 0:
            self.defs.add(node.name)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in node.args.defaults:
            self.visit(default)
        for default in node.args.kw_defaults:
            if default is not None:
                self.visit(default)
        self._scope_depth += 1
        for child in node.body:
            self.visit(child)
        self._scope_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if self._scope_depth == 0:
            self.defs.add(node.name)
        for decorator in node.decorator_list:
            self.visit(decorator)
        for base in node.bases:
            self.visit(base)
        self._scope_depth += 1
        for child in node.body:
            self.visit(child)
        self._scope_depth -= 1

    # --- comprehensions (their loop vars don't leak) ---------------------

    def _visit_comprehension(self, node: ast.AST) -> None:
        self._scope_depth += 1
        self.generic_visit(node)
        self._scope_depth -= 1

    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension
    visit_DictComp = _visit_comprehension
