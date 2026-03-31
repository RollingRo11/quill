# Quill

**Marimo Notebooks for CLI Agents**

Give [Claude Code](https://claude.ai/claude-code), [Codex](https://openai.com/index/codex/), and [Gemini CLI](https://github.com/google-gemini/gemini-cli) agents access to [marimo](https://marimo.io) notebooks.

Quill launches your favorite AI coding agent with an [MCP](https://modelcontextprotocol.io/) server that provides tools for creating and executing code in marimo notebooks. All code the agent writes is saved as reactive marimo `.py` notebooks — git-friendly, executable, and interactive.

## Installation

```bash
uv tool install git+https://github.com/RollingRo11/quill.git
```

Or add as a project dependency:

```bash
uv add git+https://github.com/RollingRo11/quill.git
```

For development:

```bash
git clone https://github.com/RollingRo11/quill.git
cd quill
uv pip install -e .
```

## Quick Start

```bash
# Launch with Claude Code (default)
quill

# Launch with a specific provider
quill claude
quill codex
quill gemini

# Pass extra flags through to the agent CLI
quill claude -c
```

## How It Works

```
┌──────────┐       MCP (stdio)       ┌────────────────┐       stdin/stdout       ┌──────────┐
│  Agent   │◄────────────────────────►│  Quill MCP     │◄───────────────────────►│  Python  │
│ (Claude, │  start_new_session       │  Server        │  execute / output       │  Process │
│  Codex,  │  execute_code            │                │                         │          │
│  Gemini) │  add_markdown ...        │  ┌───────────┐ │                         └──────────┘
│          │                          │  │  Marimo   │ │
└──────────┘                          │  │  Writer   │ │
                                      │  └─────┬─────┘ │
                                      └────────┼───────┘
                                               │
                                               ▼
                                        notebook.py
                                      (marimo format)
```

1. `quill` starts your chosen AI agent with an MCP server attached
2. The agent uses MCP tools to create sessions, execute code, and add documentation
3. Code runs in a lightweight persistent Python subprocess (no Jupyter dependency) with stdout capture, expression evaluation, and matplotlib image hooks
4. All code and markdown is saved as a marimo `.py` notebook

## Example Conversation

```
You: Create a notebook that explores the iris dataset with some visualizations.

Agent: [calls start_new_session("iris_exploration.py", "Iris Dataset Exploration")]
       → Session started. Notebook: iris_exploration.py

Agent: [calls execute_code("import pandas as pd\nfrom sklearn.datasets import load_iris\n\niris = load_iris()\ndf = pd.DataFrame(iris.data, columns=iris.feature_names)\ndf['species'] = iris.target")]
       → [Cell 0]
         (no output)

Agent: [calls execute_code("df.describe()")]
       → [Cell 1]
                sepal length (cm)  sepal width (cm)  ...
         count         150.000000        150.000000  ...
         mean            5.843333          3.057333  ...
         ...

Agent: [calls add_markdown("## Distribution of Features\nLet's visualize ...")]
       → Markdown cell added at index 2.

Agent: [calls execute_code("import matplotlib.pyplot as plt\ndf.hist(figsize=(10, 8))\nplt.tight_layout()\nplt.show()")]
       → [Cell 3]
         [1 image(s) generated]

Agent: [calls shutdown_session()]
       → Session shut down. Notebook saved to iris_exploration.py
```

The resulting `iris_exploration.py` is a valid marimo notebook:

```bash
marimo edit iris_exploration.py
```

## Available MCP Tools

| Tool | Description |
|------|-------------|
| `start_new_session` | Create a new marimo notebook and start a Python kernel |
| `resume_session` | Load an existing notebook and re-execute cells to restore state |
| `continue_session` | Fork from an existing notebook into a new file |
| `execute_code` | Run Python code and append it as a notebook cell |
| `add_markdown` | Add a markdown documentation cell (rendered via `mo.md()`) |
| `edit_cell` | Replace and re-execute an existing cell by index |
| `shutdown_session` | Save the notebook and shut down the kernel |

### Tool Details

#### `start_new_session(notebook_path, session_name?)`

Creates a fresh `.py` notebook and starts a Python subprocess. The `session_name` becomes the notebook's `app_title`.

#### `resume_session(notebook_path)`

Opens an existing marimo notebook, parses its cells, and re-executes all code cells to restore kernel state. Useful for continuing where you left off.

#### `continue_session(source_notebook_path, new_notebook_path)`

Forks a notebook: reads cells from the source, creates a copy at the new path, and re-executes everything. The original notebook is untouched.

#### `execute_code(code, cell_name?)`

Runs arbitrary Python code in the kernel. The code is appended as a new `@app.cell` in the marimo notebook. Returns stdout, the repr of the last expression, error tracebacks, and image counts.

#### `add_markdown(text, cell_name?)`

Adds a markdown cell wrapped in `mo.md()`. Does not execute anything — purely documentation.

#### `edit_cell(cell_index, new_code)`

Replaces an existing cell's code (by 0-based index) and re-executes it. The notebook file is updated.

#### `shutdown_session()`

Finalizes the notebook file and shuts down the Python subprocess.

## Why Marimo?

Unlike Jupyter notebooks (`.ipynb`), marimo notebooks are:

- **Pure Python** — stored as `.py` files, not JSON blobs
- **Git-friendly** — clean diffs, easy code review, no merge conflicts on output metadata
- **Reactive** — cells automatically re-run when their dependencies change
- **Executable** — run directly with `python notebook.py`
- **Interactive** — open with `marimo edit` for a full notebook UI with sliders, dropdowns, and more

## Providers

### Claude Code (default)

```bash
quill claude
```

Quill writes an MCP config and settings file to `~/.quill/sessions/`, then launches `claude` with `--mcp-config` and `--settings` flags. All Quill MCP tools are automatically allowed.

### Codex

```bash
quill codex
```

Passes the MCP server config via the `-c` flag to `codex`.

### Gemini CLI

```bash
quill gemini
```

Writes the MCP server config to `.gemini/settings.json` in the current directory, then launches `gemini`.

### Passing Extra Arguments

Any extra flags are forwarded to the underlying agent CLI:

```bash
quill claude --verbose
quill codex --model o4-mini
```

## Security Note

Quill gives AI agents the ability to **execute arbitrary Python code** on your machine via a Python subprocess. The code runs with the same permissions as your user account. Review generated code before trusting it, especially when working with sensitive data or system operations.

## Requirements

- Python >= 3.10
- One of: [Claude Code](https://claude.ai/claude-code), [Codex CLI](https://github.com/openai/codex), or [Gemini CLI](https://github.com/google-gemini/gemini-cli)

## License

MIT
