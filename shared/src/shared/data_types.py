from annotated_types import Ge

from contextvars import ContextVar
import os
import typing as t

type LineNo = t.Annotated[int, Ge(0)]


DEBUG = ContextVar(
    "DEBUG", default=os.environ.get("DEBUG", "false").lower in ("true", "t")
)
COMPILER = ContextVar("Compiler", default=os.environ.get("COMPILER", "gcc"))
"""
It's a context var that defaults to the env-variable or gcc


It's a context var just in case there's a weird command that works only for gcc
but not clang or whatever
"""
