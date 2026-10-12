"""Golden fixture: basic Python symbols, imports, docstrings, calls."""
import os
from helpers import util


class Greeter:
    """Says hello."""

    def __init__(self, name: str):
        self.name = name

    def hello(self) -> str:
        """Return a greeting."""
        return util.shout(self.name)


def add(a: int, b: int = 1) -> int:
    return a + b + len(os.getcwd())
