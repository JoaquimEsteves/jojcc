"""
New shit in underscore
```
program = Program(function_definition)
function_definition = Function(identifier name, instruction* instructions)
instruction = Mov(operand src, operand dst)
            | Unary(unary_operator, operand)
            | _Binary(binary_operator, operand, operand)_
            | _Idiv(operand)_
            | _Cdq_
            | AllocateStack(int)
            | Ret
unary_operator = Neg | Not
binary_operator = _Add | Sub | Mult_
operand = Imm(int) | Reg(reg) | Pseudo(identifier) | Stack(int)
reg = AX | _DX_ | R10 | _R11_
```
"""

import typing as t

from pathlib import Path
from pydantic import BaseModel, RootModel, model_validator

from chapter3 import parser
from chapter3 import tacky
from shared import data_types as dt


class Ass(RootModel[str]):
    pass


class Program(BaseModel):
    function: Function

    @staticmethod
    def from_tacky(prog: tacky.Program):
        return Program(function=Function.from_tacky(prog.function_def))

    def to_assembly(self) -> list[str]:
        return [*self.function.to_assembly(), '.section .note.GNU-stack,"",@progbits']


class Function(BaseModel):
    name: str
    instructions: list[Instruction]

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
                    operation=operation,
                    source=source,
                    destination=destination,
                ):
                    src = get_val(source)
                    dest = get_val(destination)
                    instructions.extend(
                        [
                            *Mov.new(src=src, dest=dest),
                            Unary(op=operation, operand=dest),
                        ]
                    )
                case tacky.BinaryOp(
                    operation=operation,
                    src1=src1,
                    src2=src2,
                    dest=dest,
                ):
                    src1 = get_val(src1)
                    src2 = get_val(src2)
                    dest = get_val(dest)
                    match operation:
                        case "FORWARD_SLASH" | "PERCENT":
                            # Division/remainder - are a bit of an ass
                            # `idiv` slapts the result in `EAX` and the remainder in `EDX`
                            instructions.extend(
                                [
                                    Mov(src=src1, dest=Reg(root="AX")),
                                    Cdq(),
                                    Idiv(root=src2),
                                    Mov(
                                        src=Reg(
                                            root="AX"
                                            if operation == "FORWARD_SLASH"
                                            else "DX"
                                        ),
                                        dest=dest,
                                    ),
                                ]
                            )
                        case _:
                            instructions.extend(
                                [
                                    *Mov.new(src=src1, dest=dest),
                                    Binary(op=operation, src=src2, dest=dest),
                                ]
                            )

        stack_allocation.root = stack_pointer
        return Function(name=func.name, instructions=instructions)

    def to_assembly(self) -> list[str]:
        res = [
            f".globl\t{self.name}",
            f".type\t{self.name}, @function",
            f"{self.name}:",
            "\tpushq    %rbp",
            "\tmovq     %rsp, %rbp",
        ] + [i.to_assembly() for i in self.instructions]

        return res


type Instruction = Mov | Unary | AllocateStack | Return | Idiv | Cdq | Binary


class Mov(BaseModel):
    src: Operand
    dest: Operand

    @staticmethod
    def new(src: Operand, dest: Operand) -> list[Mov]:
        if isinstance(src, Stack) and isinstance(dest, Stack):
            # It's illegal to mov from one mem-address into another
            # So we need to move to a strach register
            scratch = Reg.get_scratch()
            return [
                Mov(src=src, dest=scratch),
                Mov(src=scratch, dest=dest),
            ]
        return [Mov(src=src, dest=dest)]

    @model_validator(mode="after")
    def assert_no_illegal(self):
        match (self.src, self.dest):
            case (Stack(), Stack()):
                raise ValueError("You can't move from one memory address to another!")
            case (Imm(), Imm()):
                raise ValueError("You can't move one constant on top of another!")
            case _:
                return self

    def to_assembly(self, type: t.Literal["l", "b"] = "l") -> str:
        # In the future - the type will be inferred according to the src/dest
        return f"\tmov{type} {self.src.to_assembly()}, {self.dest.to_assembly()}"


class Unary(BaseModel):
    op: t.Literal["COMPLEMENT", "MINUS"]
    operand: Operand

    def to_assembly(self) -> str:
        op = "not" if self.op == "COMPLEMENT" else "neg"
        return f"\t{op}l {self.operand.to_assembly()}"


class Binary(BaseModel):
    op: parser.Simple_Binary
    src: Operand
    dest: Operand

    def to_assembly(self) -> str:
        ass_op = self.match_op(self.op)
        match (self.op, self.src, self.dest):
            case "ASTERISK", _, Stack():
                scratch = Reg.get_scratch("R11")
                pre = Mov(src=self.dest, dest=scratch)
                after = Mov(src=scratch, dest=self.dest)
                return (
                    f"{pre.to_assembly()}\n"
                    f"\t{ass_op} {self.src.to_assembly()}, {scratch.to_assembly()}\n"
                    f"{after.to_assembly()}"
                )
            case "LEFT_SHIFT" | "RIGHT_SHIFT", source, dest if not isinstance(
                source, Imm
            ):
                # Left and right shift have a special rule
                # From the manual: https://www.felixcloutier.com/x86/sal:sar:shl:shr
                # > The destination operand can be a register or a memory
                # > location. The count operand can be an immediate value or
                # > the CL register

                # The source must be either a constant, or on the special %CL register
                scratch = Reg.get_scratch("CL")
                pre = Mov(src=self.src, dest=scratch)
                return (
                    # Said special `cl` register must be moved with `movb`?????
                    # Apparently the `CL` is a byte-sized register
                    # So we must move a bite
                    f"{pre.to_assembly('b')}\n"
                    f"\t{ass_op} {scratch.to_assembly()}, {dest.to_assembly()}\n"
                )
            case _, Stack(), Stack():
                scratch = Reg.get_scratch()
                pre = Mov(src=self.src, dest=scratch)
                return (
                    f"{pre.to_assembly()}\n"
                    f"\t{ass_op} {scratch.to_assembly()}, {self.dest.to_assembly()}"
                )

            case _:
                return f"\t{ass_op} {self.src.to_assembly()}, {self.dest.to_assembly()}"

    @staticmethod
    def match_op(op: parser.Simple_Binary):
        match op:
            case "MINUS":
                return "subl"
            case "PLUS":
                return "addl"
            case "ASTERISK":
                return "imull"
            case "LEFT_SHIFT":
                return "sall"
            case "RIGHT_SHIFT":
                return "sarl"
            case "AMPERSAND":
                return "andl"
            case "PIPE":
                return "orl"
            case "CARRET":
                return "xorl"


class Idiv(BaseModel):
    root: Operand

    def to_assembly(self) -> str:
        """
        Note: I slapped the transformations here as opposed to the larger
        `Function.from_tacky`.

        I _think_ it makes sense? I dunno, could use some cleanup
        """
        match self.root:
            case Imm():
                # You can't divide a constant value
                # It must first go into the scratch register
                scratch = Reg.get_scratch()
                return (
                    f"{Mov(src=self.root, dest=scratch).to_assembly()}\n"
                    f"\tidivl {scratch.to_assembly()}"
                )
            case Reg() | Stack():
                return f"\tidivl {self.root.to_assembly()}"


class Cdq(BaseModel):
    def to_assembly(self) -> str:
        return "\tcdq"


class AllocateStack(BaseModel):
    root: int = 0

    def to_assembly_only_rbp(self) -> str:
        return f"\tsubq ${abs(self.root)}, %rbp"

    def to_assembly(self) -> str:
        if dt.USE_ONLY_RBP.get():
            return f"\tsubq ${abs(self.root)}, %rbp"
        return f"\tsubq ${abs(self.root)}, %rsp"


class Return(BaseModel):
    def to_assembly(self) -> str:
        return "\t\n".join(
            [
                "" if dt.USE_ONLY_RBP.get() else "\tmovq %rbp, %rsp",
                "\tpopq	%rbp",
                "\tret",
            ]
        )


type Operand = Imm | Reg | Stack


class Imm(BaseModel):
    root: int

    def to_assembly(self) -> str:
        return f"${self.root}"


class Reg(BaseModel):
    root: t.Literal[
        "AX",
        "R10",
        "R11",
        "DX",
        "CL",  # Special for left-right-shift
    ]

    @staticmethod
    def get_scratch(which: t.Literal["R10", "R11", "CL"] = "R10"):
        return Reg(root=which)

    def to_assembly(self) -> str:
        match self.root:
            case "AX":
                return "%eax"
            case "DX":
                return "%edx"
            case "R10":
                return "%r10d"
            case "R11":
                return "%r11d"
            case "CL":
                return "%cl"


class Stack(BaseModel):
    root: int

    def to_assembly(self) -> str:
        return f"{self.root}(%rbp)"


def parsed_to_assembly_construct(prog: tacky.Program):
    return Program.from_tacky(prog)


def to_assembly(filename: Path, prog: Program) -> Ass:
    """
    Since there's always just the one function...
    """
    resp = [f'.file\t"{filename.name}"', ".text", *prog.to_assembly()]

    return Ass("\n".join(resp) + "\n")
