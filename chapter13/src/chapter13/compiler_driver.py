#!/usr/bin/env -S uv run --script
import sys
import typing as t
from pathlib import Path
import argparse
import re
import subprocess
from textwrap import dedent

from pydantic import RootModel

from chapter13 import tacky
from chapter13.lexer import lex
import chapter13.parser as parser
import chapter13.codegen as codegen
import chapter13.semantic_analysis as semantic_analysis
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


def compile_but_no_link(
    filename: Path,
    ass: codegen.Ass,
    output_file: Path | None,
    lib_for_linker: list[str],
    *,
    keep_assembly: bool,
):
    assembly_path = _file_extensions(filename, ".c$", "s")
    output_file = output_file or _file_extensions(filename, ".c$", "o")

    with open(assembly_path, "w") as f:
        _ = f.write(ass.root)

    _ = subprocess.run(
        [
            dt.COMPILER.get(),
            "-c",
            str(assembly_path),
            "-o",
            str(output_file),
            *[f"-l{lib}" for lib in lib_for_linker],
        ],
        check=True,
    )
    if keep_assembly:
        print(f"Keeping {assembly_path} for you!")
    else:
        assembly_path.unlink()

    assert output_file.exists(), "What happened yo?"
    return output_file


def link(
    filenames: list[Path],
    asses: list[codegen.Ass],
    output_file: Path | None,
    lib_for_linker: list[str],
    *,
    keep_assembly: bool,
):
    assembly_paths: list[Path] = []
    for filename, ass in zip(filenames, asses, strict=True):
        assembly_path = _file_extensions(filename, ".c$", "s")
        if output_file is None:
            # just grab the first one lol
            output_file = _file_extensions(filename, ".c$", "")

        with open(assembly_path, "w") as f:
            _ = f.write(ass.root)
        assembly_paths.append(assembly_path)

    assert output_file, "What happened yo?"
    _ = subprocess.run(
        [
            dt.COMPILER.get(),
            *map(str, assembly_paths),
            "-o",
            str(output_file),
            *[f"-l{lib}" for lib in lib_for_linker],
        ],
        check=True,
    )

    if keep_assembly or dt.DEBUG.get():
        print(f"🐛 Keeping {', '.join(map(str, assembly_paths))} for you! 🐛")
    else:
        for p in assembly_paths:
            p.unlink()

    assert output_file.exists(), "What happened yo?"
    return output_file


def _file_extensions(input_file: Path, remove: str, new: str):
    assert input_file.exists(), "Dude - where is the file?"
    tweaked_name = re.sub(remove, "", input_file.name)
    if new:
        tweaked_name = f"{tweaked_name}.{new}"

    return input_file.parent / f"{tweaked_name}"


class Args(t.NamedTuple):
    filenames: list[Path]
    lex: bool
    parse: bool
    validate: bool
    codegen: bool
    tacky: bool
    S: bool
    c: bool
    keep_assembly: bool
    lib_for_linker: list[str]
    o: Path | None


def _arg_parse():
    parser = argparse.ArgumentParser(
        prog="jojcc",
        description="Joaquim's Own Jank C Compiler",
    )

    _ = parser.add_argument(
        "--lex",
        action="store_true",
        help=dedent("""\
            Run the lexer, but stop before parsing
        """),
    )
    _ = parser.add_argument(
        "-l",
        "--lib-for-linker",
        action="append",
        metavar=("<lib>"),
        help=dedent("""\
            Add a lib when linking. You can pass multiple libs.
        """),
    )
    _ = parser.add_argument(
        "-k",
        "--keep-assembly",
        action="store_true",
        help=dedent("""\
            Normally we'd delete assembly files; but we can keep them around just for you!
        """),
    )
    _ = parser.add_argument(
        "-p",
        "--parse",
        action="store_true",
        help=dedent("""\
            Run the lexer & parser, but stop before assembly generation
        """),
    )

    _ = parser.add_argument(
        "--validate",
        action="store_true",
        help=dedent("""\
            Run the lexer & parser & semantic analysis, but stop before assembly generation
        """),
    )
    _ = parser.add_argument(
        "--tacky",
        action="store_true",
        help=dedent("""\
            Run the lexer & parser & semantic analysis & tacky, but stop before assembly generation
        """),
    )
    _ = parser.add_argument(
        "--codegen",
        action="store_true",
        help=dedent("""\
            Run the lexer & parser & semantic analysis & tacky & assembly generation, but stop before code emission
        """),
    )

    _ = parser.add_argument(
        "-S",
        action="store_true",
        help=dedent("""\
            Emit an assembly file, but don't assemble or link it.
        """),
    )

    _ = parser.add_argument(
        "-c",
        action="store_true",
        help=dedent("""\
            Compile and assemble, but do not link
        """),
    )

    _ = parser.add_argument(
        "-o",
        nargs="?",
        help=dedent("""\
            Place the output file into <file>
        """),
    )

    _ = parser.add_argument("filenames", nargs="+")

    args = parser.parse_args()
    filename = [Path(f) for f in args.filenames]  # pyright: ignore[reportAny]
    assert all(f.exists() for f in filename), "{filename=} not found"
    o = Path(args.o) if args.o else None  # pyright: ignore[reportAny]
    return Args(
        **(args.__dict__ | {"filenames": filename, "o": o}),
    )


type AST = list[str]


def lexer(input: Path):
    pre = preprocess(input)
    with open(pre.root) as f:
        return pre, lex(f.read(), input)


def main():
    (
        filenames,
        lex,
        parse,
        validate_f,
        codegen_f,
        tacky_f,
        S_flag,
        c_flag,
        keep_assembly,
        lib_for_linker,
        output_file,
    ) = _arg_parse()

    if output_file and len(filenames) > 1 and any((c_flag, S_flag)):
        raise ValueError(
            "cannot specify `-o` with `-c`, `-S` or `-E` with multiple files"
        )

    full_assembly: list[codegen.Ass] = []
    also_link = not any((lex, parse, validate_f, codegen_f, tacky_f, S_flag, c_flag))
    for filename in filenames:
        _ = dt.CURRENT_FILE.set(filename)
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
            continue
        parsed = parser.Program.from_tokens(lexed)
        if parse:
            print(parsed)
            continue
        if validate_f:
            print("Before")
            print(parsed)
            print("After")
            validated = semantic_analysis.resolve_program(parsed)
            print(validated)
            continue
        parsed = semantic_analysis.resolve_program(parsed)

        tackified = tacky.Program.from_ast(parsed)
        if tacky_f:
            print(tackified)
            continue
        assembly_ast = codegen.parsed_to_assembly_construct(tackified)
        if codegen_f:
            print(assembly_ast)
            continue
        assembly_str = codegen.to_assembly(filename, assembly_ast)
        full_assembly.append(assembly_str)
        if S_flag:
            if output_file:
                with open(output_file, "w") as f:
                    _ = f.write(assembly_str.root)
            else:
                print(assembly_str.root)
            continue

        if c_flag:
            object_file = compile_but_no_link(
                filename,
                assembly_str,
                output_file,
                lib_for_linker,
                keep_assembly=keep_assembly,
            )
            print(f"🦀 Compiled to {object_file.absolute()} 🦀")
            continue

    if also_link:
        elf = link(
            filenames,
            full_assembly,
            output_file,
            lib_for_linker,
            keep_assembly=keep_assembly,
        )
        print(f"🦀 Compiled to {elf.absolute()} 🦀")


if __name__ == "__main__":
    main()
