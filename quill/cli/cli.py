"""Main CLI entry point."""

import click

from quill.cli.commands import copilot_impl
from quill.cli.constants import DEFAULT_PROVIDER


@click.group(
    invoke_without_command=True,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Quill — Marimo Notebooks for CLI Agents"""
    if ctx.invoked_subcommand is None:
        copilot_impl(DEFAULT_PROVIDER, ctx.args)


@main.command(
    name="claude",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def claude(ctx: click.Context) -> None:
    """Launch with Claude Code."""
    copilot_impl("claude", ctx.args)


@main.command(
    name="codex",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def codex(ctx: click.Context) -> None:
    """Launch with Codex."""
    copilot_impl("codex", ctx.args)


@main.command(
    name="gemini",
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.pass_context
def gemini(ctx: click.Context) -> None:
    """Launch with Gemini CLI."""
    copilot_impl("gemini", ctx.args)
