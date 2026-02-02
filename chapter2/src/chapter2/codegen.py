"""

```asdl
program = Program(function_definition)
function_definition = Function(identifier name, instruction* instructions)
instruction = Mov(operand src, operand dst) | Ret
operand = Imm(int) | Register
```


```
| AST node                     | Assembly construct           |
| ---                          | ---                          |
| Program(function_definition) | Program(function_definition) |
| Function(name, body)         | Function(name, instructions) |
| Return(exp)                  | Mov(exp, Register) Ret       |
| Constant(int)                | Imm(int)
```
"""

from pathlib import Path
from pydantic import BaseModel, RootModel

from chapter2 import parser


class Ass(RootModel[str]):
    pass


class Program(BaseModel):
    function: "Function"


class Function(BaseModel):
    name: str
    instructions: "list[Return]"


class Return(RootModel[parser.ReturnStatement]):
    pass


def parsed_to_assembly_construct(prog: parser.Program):
    return Program(
        function=Function(
            name=prog.function.name.root,
            instructions=[prog.function.body.root],  # pyright: ignore[reportArgumentType]
        )
    )


def to_assembly(filename: Path, prog: Program) -> Ass:
    """
    Since there's always just the one function...
    """
    label = prog.function.name
    resp: list[str] = [
        f'\t.file\t"{filename.name}"',
        "\t.text",
        f"\t.globl\t{label}",
        f"\t.type\t{label}, @function",
        f"{label}:",
        f"\t movl ${prog.function.instructions[0].root.exp.root}, %eax",
        "\t ret",
        f"\t.size	{label}, .-{label}",
        '\t.section\t.note.GNU-stack,"",@progbits',
    ]

    return Ass("\n".join(resp) + "\n")
