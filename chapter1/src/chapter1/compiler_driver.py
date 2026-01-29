#!/usr/bin/env -S uv run
import typing as t
from pathlib import Path
import argparse
import re
import subprocess
from textwrap import dedent

from chapter1.lexer import lex
import chapter1.parser as parser
from shared import data_types as dt


class PreProcessed(Path):
    pass


class Ass(Path):
    pass


class Elf(Path):
    pass


def preprocess(input_file: Path) -> PreProcessed:
    assert input_file.exists(), "Dude - where is the file?"
    # Traditionally PREPROCESSED_FILES have the `.i` extension
    output_file = _file_extensions(input_file, ".c$", "i")

    _ = subprocess.run(
        [dt.COMPILER.get(), "-E", "-P", str(input_file), "-o", str(output_file)],
        check=True,
    )

    return PreProcessed(output_file)


def preprocessed_to_assembly(
    pre: PreProcessed,
    _assembly: str,
) -> Ass:
    """
    AKA: code-emission
    """
    output_file = _file_extensions(pre, ".i$", "s")
    output_file.touch()
    return Ass(output_file)


def link(ass: Ass) -> Elf:
    # Traditionally PREPROCESSED_FILES have the `.i` extension
    output_file = _file_extensions(ass, ".s$", "")
    _ = subprocess.run(
        [dt.COMPILER.get(), "-E", "-P", str(ass), "-o", str(output_file)],
        check=True,
    )
    assert output_file.exists(), "What happened yo?"
    ass.unlink()
    return Elf(output_file)


def _file_extensions(input_file: Path, remove: str, new: str):
    assert input_file.exists(), "Dude - where is the file?"
    tweaked_name = re.sub(remove, "", input_file.name)
    if new:
        tweaked_name = f"{tweaked_name}.{new}"

    return input_file.parent / f"{tweaked_name}"


class Args(t.NamedTuple):
    filename: Path
    lex: bool
    parse: bool
    codegen: bool
    S: bool


def _arg_parse():
    parser = argparse.ArgumentParser(
        prog="jojcc",
        description="Joaquim's Own Jank C Compiler",
    )

    _ = parser.add_argument("filename")
    _ = parser.add_argument(
        "--lex",
        action="store_true",
        help=dedent("""\
            Run the lexer, but stop before parsing
        """),
    )
    _ = parser.add_argument(
        "--parse",
        action="store_true",
        help=dedent("""\
            Run the lexer & parser, but stop before assembly generation
        """),
    )
    _ = parser.add_argument(
        "--codegen",
        action="store_true",
        help=dedent("""\
            Run the lexer & parser & assembly generation, but stop before code emission
        """),
    )

    # It's a TODO for future chapters
    _ = parser.add_argument(
        "-S",
        action="store_true",
        help=dedent("""\
            Emit an assembly file, but don't assemble or link it.
        """),
    )

    args = parser.parse_args()
    filename = Path(args.filename)  # pyright: ignore[reportAny]
    assert filename.exists(), "{filename=} not found"
    return Args(
        **(args.__dict__ | {"filename": filename}),
    )


type AST = list[str]


def lexer(input: Path):
    pre = preprocess(input)
    with open(pre, "r") as f:
        return pre, lex(f.read())


def assembly_generation(_ast: parser.Program) -> str:
    return ""


def code_emission(filename: PreProcessed, _assembly: str) -> Ass:
    return preprocessed_to_assembly(filename, _assembly)


def main():
    filename, lex, parse, codegen, _S = _arg_parse()
    match (lex, parse, codegen):
        case (True, False, False):
            pre, lexed = lexer(filename)
            pre.unlink()
            print(lexed)
            return
        case (False, True, False):
            pre, lexed = lexer(filename)
            pre.unlink()
            print(parser.Program(lexed))
            return
        case (False, False, True):
            pre, lexed = lexer(filename)
            pre.unlink()
            ass = preprocessed_to_assembly(
                pre, assembly_generation(parser.Program(lexed))
            )
            print(ass)
        case (False, False, False):
            pre, lexed = lexer(filename)
            pre.unlink()
            ass = preprocessed_to_assembly(
                pre, assembly_generation(parser.Program(lexed))
            )
            print(link(ass))
        case _:
            raise ValueError("Nope")
    breakpoint()


if __name__ == "__main__":
    main()
