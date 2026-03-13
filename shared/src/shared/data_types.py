from pathlib import Path
from annotated_types import Ge
from shutil import which

from contextvars import ContextVar
import os
import typing as t

from pydantic import Field

type uInt = t.Annotated[int, Ge(0)]
type Positive_Int = t.Annotated[int, Ge(1)]
type LineNo = uInt
type CharNo = uInt


Identifier_Pattern = r"[a-zA-Z0-9_\.]"
Identifier = t.Annotated[str, Field(pattern=rf"^[_a-zA-Z]{Identifier_Pattern}*$")]
"""
Only letters, digits, periods, and underscores
Must start with a letter
"""


USE_ONLY_RBP = ContextVar(
    "USE_ONLY_RBP",
    default=os.environ.get("USE_ONLY_RBP", "false").lower() in ("true", "t"),
)
"""
Funnily enough - the Registry-Stack-Pointer is a little bit useless
We can do the whole thing with just `rbp`
(Don't ask me how this works...)
(In fact - it ONLY works if I _just_ use the `rbp`, DON'T ASK ME WHY EITHER)
"""

DEBUG = ContextVar(
    "DEBUG", default=os.environ.get("DEBUG", "false").lower() in ("true", "t")
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

CAT_PROGRAM = (which("bar") and "bat") or (which("batcat") and "batcat") or "cat"
"""
External "pretty" program to print to terminal
"""

Oldest_School_Registers = t.Literal[
    "A",  # A -> ACCUMULATOR (for return values)
    "B",  # Base
    "C",  # Counter
    "D",  # Data
]
"""
All the way from 1972!
Crazy to think about that if this was released in 2026 we'd now be in 2080.
"""
# fmt: on


# fmt: off
Old_School_Registers = t.Literal[
    "SP", # Stack Pointer
    "BP", # Base Pointer
    "SI", # Source Index
    "DI", # Destination Index
]
# fmt: on

New_School_Registers = t.Literal[
    "R8",  # just boring numbers with no mnemonic
    "R9",  # Definitely more sane...but still
    "R10",
    "R11",
    "R12",
    "R13",
    "R14",
    "R15",
]


@t.final
class x64:
    type Register = (
        Oldest_School_Registers | Old_School_Registers | New_School_Registers
    )
    type Bit_Size = t.Literal[64, 32, 16, 8]
    type Operation_Size = t.Literal["q", "l", "w", "b"]
    """
    b -> 1 byte
    w -> word (2 bytes)
    l -> long? Sometimes it's also double
    q -> Quad, 4 bytes
    """

    from_bit_size: t.Final[dict[Bit_Size, Operation_Size]] = {
        64: "q",
        32: "l",
        16: "w",
        8: "b",
    }
    from_op_size: t.Final[dict[Operation_Size, Bit_Size]] = {
        val: key for key, val in from_bit_size.items()
    }

    from_arg_number: t.Final[dict[int, Register]] = {
        0: "DI",
        1: "SI",
        2: "D",
        3: "C",
        4: "R8",
        5: "R9",
    }
    """
    SYSTEM V Call Convention
    Arg 1 goes into DI, Arg 2 into SI, etc

    Does it make _ANY_ sense to the reader? 'cos it FOR SURE doesn't for me.
    OK so `A` is the accumulator sure, but then why do we skip right to DI only to come _back_ to D and C?
    And then we say "fuck it" and jump right into the R8 and R9 register...
    """

    NUMBER_OF_REGISTER_ARGUMENTS = len(from_arg_number)
    """
    6
    """

    max: t.Final[dict[Bit_Size, int]] = {
        size: 2 ** (size - 1) - 1 for size in from_bit_size
    }
    umax: t.Final[dict[Bit_Size, int]] = {size: 2**size for size in from_bit_size}
