from pathlib import Path
from annotated_types import Ge
from shutil import which

from contextvars import ContextVar
import os
import typing as t

from pydantic import Field

type LineNo = t.Annotated[int, Ge(0)]
type CharNo = LineNo


Identifier_Pattern = r"[a-zA-Z0-9_\.]"
Identifier = t.Annotated[str, Field(pattern=rf"^[a-zA-Z]{Identifier_Pattern}*$")]
"""
Only letters, digits, periods, and underscores
Must start with a letter
"""


USE_ONLY_RBP = ContextVar(
    "USE_ONLY_RBP",
    default=os.environ.get("USE_ONLY_RBP", "false").lower in ("true", "t"),
)
"""
Funnily enough - the Registry-Stack-Pointer is a little bit useless
We can do the whole thing with just `rbp`
(Don't ask me how this works...)
"""

DEBUG = ContextVar(
    "DEBUG", default=os.environ.get("DEBUG", "false").lower in ("true", "t")
)
COMPILER = ContextVar("Compiler", default=os.environ.get("COMPILER", "gcc"))
"""
It's a context var that defaults to the env-variable or gcc


It's a context var just in case there's a weird command that works only for gcc
but not clang or whatever
"""

CURRENT_FILE: ContextVar[Path] = ContextVar("CURRENT_FILE", default=Path("/dev/null"))
"""
For better error messages
"""

INDENT_LEVEL = ContextVar("INDENT_LEVEL", default=0)

if which("bat"):
    CAT_PROGRAM = "bat"
elif which("batcat"):
    CAT_PROGRAM = "batcat"  # pyright: ignore[reportConstantRedefinition]
else:
    CAT_PROGRAM = "cat"  # pyright: ignore[reportConstantRedefinition]
