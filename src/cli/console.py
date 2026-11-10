import sys
from collections.abc import Callable

import click
from rich.console import Console
from rich.text import Text


console = Console()

# Same keys as the HTML report's CSS classes
CHANGE_STYLES = {'up': 'bold red', 'down': 'bold green', 'flat': 'dim'}


def signed_style(value: float) -> str:
    return CHANGE_STYLES['up' if value > 0 else 'down' if value < 0 else 'flat']


def ask(prompt: str) -> str:
    return console.input(Text(f"{prompt}: ", style="cyan")).strip()


def choose(prompt: str, options: dict[str, str], show_options: bool = True) -> str:
    """Pick an option with a single keypress and return its key.\n
    Falls back to a typed line when stdin is not a terminal (pipes, tests).
    """
    if show_options:
        separator = " " if prompt.endswith("?") else ": "
        prompt += separator + " / ".join(_option_label(key, label) for key, label in options.items())
    tty = sys.stdin.isatty()
    while True:
        if tty:
            console.print(Text(f"{prompt}: ", style="cyan"), end="")
            key = click.getchar().lower()
        else:
            key = ask(prompt).lower()
        if key in options:
            if tty:
                console.print(options[key])
            return key
        if tty:
            console.print()
        warn("Invalid input, please try again...")


def _option_label(key: str, label: str) -> str:
    """'[t]icker' when the label starts with its key, '[1] RSI' otherwise."""
    if key.isalpha() and label[:1].lower() == key:
        return f"[{label[0]}]{label[1:]}"
    return f"[{key}] {label}"


def run_interactive(main: Callable[[], None]) -> None:
    """Run an interactive tool, leaving quietly on Ctrl+C / Ctrl+D."""
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()
    console.print("Goodbye!")


def success(message: str) -> None:
    console.print(message, style="green", markup=False)


def warn(message: str) -> None:
    console.print(message, style="yellow", markup=False)
