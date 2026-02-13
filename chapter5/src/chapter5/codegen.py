"""
New shit in underscore
```
program = Program(function_definition)
function_definition = Function(identifier name, instruction* instructions)
instruction = Mov(operand src, operand dst)
            | Unary(unary_operator, operand)
            | Binary(binary_operator, operand, operand)
            | _Cmp(operand, operand)_
            | Idiv(operand)
            | Cdq
            | _Jmp(identifier)_
            | _JmpCC(cond_code, identifier)_
            | _SetCC(cond_code, operand)_
            | _Label(identifier)_
            | AllocateStack(int)
            | Ret
unary_operator = Neg | Not
binary_operator = Add | Sub | Mult
operand = Imm(int) | Reg(reg) | Pseudo(identifier) | Stack(int)
cond_code = _E_ | _NE_ | _G_ | _GE_ | _L_ | _LE_
reg = AX | DX | R10 | R11
```
"""

import typing as t
# import functools

from pathlib import Path
from pydantic import BaseModel, RootModel, model_validator

from chapter5 import parser
from chapter5 import tacky
from shared import data_types as dt


def to_assembly(filename: Path, prog: Program) -> Ass:
    """
    Since there's always just the one function...
    """
    resp: list[str] = [
        f'.file\t"{filename.name}"',
        ".text",
    ] + prog.to_assembly()

    return Ass("\n".join(resp) + "\n")


type Instruction = (
    Mov
    | Unary
    | AllocateStack
    | Return
    | Idiv
    | Cdq
    | Binary
    | Cmp
    | Jmp
    | JmpCC
    | SetCC
    | Label
)
type Cond_Code = t.Literal["e", "ne", "g", "ge", "l", "le"]


def map_relational_to_cond_code(code: parser.Relational_Binary) -> Cond_Code:
    match code:
        case "==":
            return "e"
        case "!=":
            return "ne"
        case "LE":
            return "le"
        case "LT":
            return "l"
        case "GT":
            return "g"
        case "GE":
            return "ge"


class Program(BaseModel):
    function: "Function"

    @staticmethod
    def from_tacky(prog: tacky.Program):
        return Program(function=Function.from_tacky(prog.function_def))

    def to_assembly(self) -> list[str]:
        return self.function.to_assembly() + [
            '.section .note.GNU-stack,"",@progbits',
        ]


type Get_Val = "t.Callable[[tacky.Value], Imm | Stack]"


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
                    src = get_val(value) if value else Imm(root=0)
                    instructions.extend([Mov(src=src, dest=Reg(root="AX")), Return()])

                case tacky.Unary():
                    instructions.extend(Unary.from_tacky(inst, get_val))

                case tacky.BinaryOp():
                    instructions.extend(Binary.from_tacky(inst, get_val))

                case tacky.Copy(src=src, dest=dest):
                    instructions.extend(Mov.new(get_val(src), get_val(dest)))

                case tacky.JumpIfZero(target=target, condition=condition):
                    instructions.extend(
                        (
                            Cmp(lhs=Imm(root=0), rhs=get_val(condition)),
                            JmpCC(cond="e", label=target),
                        )
                    )
                case tacky.JumpIfNotZero(target=target, condition=condition):
                    instructions.extend(
                        (
                            Cmp(lhs=Imm(root=0), rhs=get_val(condition)),
                            JmpCC(cond="ne", label=target),
                        )
                    )

                case tacky.Jump(target=target):
                    instructions.append(Jmp(root=target))

                case tacky.Label(identifier=identifier):
                    instructions.append(Label(root=identifier))
                    pass

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
    op: tacky.Simple_Unary
    operand: Operand

    def to_assembly(self) -> str:
        match self.op:
            case "COMPLEMENT":
                return f"\tnotl {self.operand.to_assembly()}"
            case "MINUS":
                return f"\tnegl {self.operand.to_assembly()}"

    @staticmethod
    def from_tacky(
        arg: tacky.Unary, get_val: t.Callable[[tacky.Value], Imm | Stack]
    ) -> tuple[Instruction, ...]:
        match arg:
            case tacky.Unary(
                operation="NOT",
                source=source,
                destination=destination,
            ):
                dst = get_val(destination)
                return (
                    Cmp(lhs=Imm(root=0), rhs=get_val(source)),
                    Mov(src=Imm(root=0), dest=dst),
                    SetCC(cond="e", operand=dst),  # pyright: ignore[reportArgumentType]
                )

            case tacky.Unary(
                operation=operation,
                source=source,
                destination=destination,
            ):
                src = get_val(source)
                dest = get_val(destination)
                return (
                    *Mov.new(src=src, dest=dest),
                    Unary(
                        op=operation,  # pyright: ignore[reportArgumentType]
                        operand=dest,
                    ),
                )


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
            case "PLUS" | "MINUS" | "ASTERISK" | "LEFT_SHIFT" | "RIGHT_SHIFT", _, Imm():
                raise ValueError(
                    "Bad assembly! Destination can't be a constant! It holds the result"
                )
            case "LEFT_SHIFT" | "RIGHT_SHIFT", Reg() | Stack(), dest:
                # Left and right shift have a special rule
                # From the manual: https://www.felixcloutier.com/x86/sal:sar:shl:shr
                # > The destination operand can be a register or a memory
                # > location. The count operand can be an immediate value or
                # > the CL register

                # The source must be either a constant, or on the special %CL register
                scratch = Reg.get_scratch("CL", 8)
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

    @staticmethod
    def from_tacky(inst: tacky.BinaryOp, get_val: Get_Val) -> tuple[Instruction, ...]:
        src1 = get_val(inst.src1)
        src2 = get_val(inst.src2)
        dest = get_val(inst.dest)
        match inst.operation:
            case "FORWARD_SLASH" | "PERCENT":
                # Division/remainder - are a bit of an ass
                # `idiv` slapts the result in `EAX` and the remainder in `EDX`
                return (
                    Mov(src=src1, dest=Reg(root="AX")),
                    Cdq(),
                    Idiv(root=src2),
                    Mov(
                        src=Reg(
                            root="AX" if inst.operation == "FORWARD_SLASH" else "DX"
                        ),
                        dest=dest,
                    ),
                )

            case "LE" | "LT" | "GT" | "GE" | "==" | "!=":
                return (
                    Cmp(lhs=src2, rhs=src1),
                    Mov(src=Imm(root=0), dest=dest),
                    SetCC(
                        cond=map_relational_to_cond_code(inst.operation),
                        operand=dest,  # pyright: ignore[reportArgumentType]
                    ),
                )

            case _arrithmetic:
                return (
                    *Mov.new(src=src1, dest=dest),
                    Binary(
                        op=inst.operation,  # pyright: ignore[reportArgumentType]
                        src=src2,
                        dest=dest,
                    ),
                )
        raise ValueError("unreachable")  # pyright: ignore[reportUnreachable]


class Cmp(BaseModel):
    lhs: Operand
    rhs: Operand

    def to_assembly(self) -> str:
        res: list[str] = []
        source = self.lhs
        dest = self.rhs

        match self.lhs, self.rhs:
            case (Stack(), Stack()):
                scratch = Reg.get_scratch()
                intermediate = Mov(src=self.lhs, dest=scratch)
                res.append(intermediate.to_assembly())
                source = scratch

            case (_, Imm()):
                # The destination can never be the right-side
                scratch = Reg.get_scratch()
                intermediate = Mov(src=self.rhs, dest=scratch)
                res.append(intermediate.to_assembly())
                dest = scratch

            case _:
                pass

        res.append(f"\tcmpl {source.to_assembly()}, {dest.to_assembly()}")
        return "\n".join(res)


class Jmp(BaseModel):
    root: dt.Identifier

    def to_assembly(self) -> str:
        return f"\tjmp {self.root}"


class JmpCC(BaseModel):
    label: dt.Identifier
    cond: Cond_Code

    def to_assembly(self) -> str:
        return f"\tj{self.cond} {self.label}"


class SetCC(BaseModel):
    operand: Stack | Reg
    cond: Cond_Code

    def to_assembly(self) -> str:
        return f"\tset{self.cond} {get_8_bit(self.operand).to_assembly()}"


class Label(BaseModel):
    root: dt.Identifier

    def to_assembly(self) -> str:
        return f"{self.root}:"


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
    size: t.Literal[32, 8] = 32

    @staticmethod
    def get_scratch(
        which: t.Literal["R10", "R11", "CL"] = "R10", size: t.Literal[32, 8] = 32
    ):
        return Reg(root=which, size=size)

    def to_assembly(self) -> str:
        match self.root, self.size:
            case "AX", 32:
                return "%eax"
            case "AX", 8:
                return "%al"
            case "DX", 32:
                return "%edx"
            case "DX", 8:
                return "%dl"
            case "R10", 32:
                return "%r10d"
            case "R10", 8:
                return "%r10b"
            case "R11", 32:
                return "%r11d"
            case "R11", 8:
                return "%r11b"
            case "CL", 8:
                return "%cl"
            case "CL", 32:
                raise ValueError("NOPE")


class Stack(BaseModel):
    root: int

    def to_assembly(self) -> str:
        return f"{self.root}(%rbp)"


def get_8_bit(operand: Stack | Reg):
    match operand:
        case Stack():
            return operand
        case Reg(root=root):
            return Reg(root=root, size=8)


def parsed_to_assembly_construct(prog: tacky.Program):
    return Program.from_tacky(prog)


class Ass(RootModel[str]):
    pass
