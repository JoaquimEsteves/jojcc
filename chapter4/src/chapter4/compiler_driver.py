#!/usr/bin/env -S uv run --script
import sys
import typing as t
from pathlib import Path
import argparse
import re
import subprocess
from textwrap import dedent

from pydantic import RootModel

from chapter4 import tacky
from chapter4.lexer import lex
import chapter4.parser as parser
import chapter4.codegen as codegen
from shared import data_types as dt


class PreProcessed(RootModel[Path]):
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


def link(filename: Path, ass: codegen.Ass):
    # Traditionally PREPROCESSED_FILES have the `.i` extension

    assembly_path = _file_extensions(filename, ".c$", "s")
    output_file = _file_extensions(filename, ".c$", "")

    with open(assembly_path, "w") as f:
        _ = f.write(ass.root)

    _ = subprocess.run(
        [dt.COMPILER.get(), str(assembly_path), "-o", str(output_file)],
        check=True,
    )
    assembly_path.unlink()

    assert output_file.exists(), "What happened yo?"
    return output_file


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
    tacky: bool
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
        "--tacky",
        action="store_true",
        help=dedent("""\
            Run the lexer & parser & tacky, but stop before assembly generation
        """),
    )
    _ = parser.add_argument(
        "--codegen",
        action="store_true",
        help=dedent("""\
            Run the lexer & parser & tacky & assembly generation, but stop before code emission
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
    assert filename.exists(), f"{filename=} not found"
    return Args(
        **(args.__dict__ | {"filename": filename}),
    )


type AST = list[str]


def lexer(input: Path):
    pre = preprocess(input)
    with open(pre.root) as f:
        return pre, lex(f.read())


def assembly_generation(_ast: codegen.Program) -> str:
    return ""


def main():
    filename, lex, parse, codegen_f, tacky_f, S_flag = _arg_parse()
    # Only 'cat' if we're outputting to a terminal
    # This allows us to run `compiler_driver.py > whatever.output`
    if sys.stdout.isatty():
        _ = subprocess.run(
            [dt.CAT_PROGRAM, str(filename)],
            check=True,
        )

    pre, lexed = lexer(filename)
    pre.root.unlink()
    if lex:
        print(lexed)
        return
    parsed = parser.Program(lexed)
    if parse:
        print(parsed)
        return
    tackified = tacky.Program.from_ast(parsed)
    if tacky_f:
        print(tackified)
        return
    assembly_ast = codegen.parsed_to_assembly_construct(tackified)
    if codegen_f:
        print(assembly_ast)
        return
    assembly_str = codegen.to_assembly(filename, assembly_ast)
    if S_flag:
        print(assembly_str.root)
        return

    elf = link(filename, assembly_str)
    print(f"compiled to {elf.absolute()}")


if __name__ == "__main__":
    main()
