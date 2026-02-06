"""
```
program = Program(function_definition)
function_definition = Function(identifier name, instruction* instructions)
instruction = Mov(operand src, operand dst)
            | Unary(unary_operator, operand)
            | AllocateStack(int)
            | Ret
unary_operator = Neg | Not
operand = Imm(int) | Reg(reg) | Pseudo(identifier) | Stack(int)
reg = AX | R10
```
"""

import typing as t
# import functools

from pathlib import Path
from pydantic import BaseModel, RootModel, model_validator

from chapter3 import parser
from chapter3 import tacky


class Ass(RootModel[str]):
    pass


class Program(BaseModel):
    function: "Function"

    @staticmethod
    def from_tacky(prog: tacky.Program):
        return Program(function=Function.from_tacky(prog.function_def))

    def to_assembly(self):
        return self.function.to_assembly() + [
            '.section .note.GNU-stack,"",@progbits',
        ]


class Function(BaseModel):
    name: str
    instructions: "list[Instruction]"

    @staticmethod
    def from_tacky(func: tacky.Function):
        stack_allocation = AllocateStack()
        instructions: list[Instruction] = [stack_allocation]

        stack_pointer = 0
        stack: dict[str, int] = {}

        def get_stack(name: str):
            nonlocal stack_pointer
            if name in stack:
                return stack[name]
            # bump the stack!
            stack_pointer -= 4
            stack[name] = stack_pointer
            return stack_pointer

        def get_val(value: tacky.Value):
            match value:
                case parser.Constant(root=val):
                    return Imm(root=val)

                case tacky.Var(name=name):
                    return Stack(root=get_stack(name))

        for inst in func.instructions:
            match inst:
                case tacky.Return(root=value):
                    src = get_val(value)
                    instructions.extend([Mov(src=src, dest=Reg(root="AX")), Return()])

                case tacky.Unary(
                    operation=operation, source=source, destination=destination
                ):
                    src = get_val(source)
                    dest = get_val(destination)
                    if isinstance(src, Stack) and isinstance(dest, Stack):
                        # It's illegal to mov from one mem-address into another
                        # So we need to move to a strach register
                        scratch = Reg(root="R10")
                        instructions.append(Mov(src=src, dest=scratch))
                        src = scratch
                    instructions.extend(
                        [Mov(src=src, dest=dest), Unary(op=operation, operand=dest)]
                    )

        stack_allocation.root = stack_pointer
        return Function(name=func.name, instructions=instructions)

    def to_assembly(self):
        res = [
            f".globl\t{self.name}",
            f".type\t{self.name}, @function",
            f"{self.name}:",
            "\tpushq    %rbp",
            "\tmovq     %rsp, %rbp",
        ] + [i.to_assembly() for i in self.instructions]

        return res


type Instruction = Mov | Unary | AllocateStack | Return


class Mov(BaseModel):
    src: Operand
    dest: Operand

    @model_validator(mode="after")
    def assert_no_illegal(self):
        match (self.src, self.dest):
            case (Stack(), Stack()):
                raise ValueError("You can't move from one memory address to another!")
            case (Imm(), Imm()):
                raise ValueError("You can't move one constant on top of another!")
            case _:
                return self

    def to_assembly(self):
        return f"\tmovl {self.src.to_assembly()}, {self.dest.to_assembly()}"


class Unary(BaseModel):
    op: t.Literal["COMPLEMENT", "NEGATION"]
    operand: Operand

    def to_assembly(self):
        op = "not" if self.op == "COMPLEMENT" else "neg"
        return f"\t{op}l {self.operand.to_assembly()}"


USE_ONLY_RBP = False
"""
Funnily enough - the Registry-Stack-Pointer is a little bit useless
We can do the whole thing with just `rbp`
(Don't ask me how this works...)
"""


class AllocateStack(BaseModel):
    root: int = 0

    def to_assembly_only_rbp(self):
        return f"\tsubq ${abs(self.root)}, %rbp"

    def to_assembly(self):
        if USE_ONLY_RBP:
            return f"\tsubq ${abs(self.root)}, %rbp"
        return f"\tsubq ${abs(self.root)}, %rsp"


class Return(BaseModel):
    def to_assembly(self):
        return "\t\n".join(
            [
                "" if USE_ONLY_RBP else "\tmovq %rbp, %rsp",
                "popq	%rbp",
                "ret",
            ]
        )


type Operand = Imm | Reg | Stack


class Imm(BaseModel):
    root: int

    def to_assembly(self):
        return f"${self.root}"


class Reg(BaseModel):
    root: t.Literal["AX", "R10"]

    def to_assembly(self):
        return f"%{'eax' if self.root == 'AX' else 'r10d'}"


class Stack(BaseModel):
    root: int

    def to_assembly(self):
        return f"{self.root}(%rbp)"


def parsed_to_assembly_construct(prog: tacky.Program):
    return Program.from_tacky(prog)


def to_assembly(filename: Path, prog: Program) -> Ass:
    """
    Since there's always just the one function...
    """
    resp: list[str] = [
        f'.file\t"{filename.name}"',
        ".text",
    ] + prog.to_assembly()

    return Ass("\n".join(resp) + "\n")
