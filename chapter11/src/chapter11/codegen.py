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

from textwrap import dedent
import typing as t
# import functools

from pathlib import Path
from pydantic import BaseModel, RootModel, model_validator

from chapter11 import parser
from chapter11 import tacky
from chapter11.semantic_analysis import SYMBOL_TABLE
from shared import data_types as dt, pure_functions as pf


def parsed_to_assembly_construct(prog: tacky.Program):
    return Program.from_tacky(prog)


def to_assembly(filename: Path, prog: Program) -> Ass:
    """
    Since there's always just the one function...
    """
    resp: list[str] = [
        f'.file\t"{filename.name}"',
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
    | Push
    | Call
    | DeAllocateStack
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
    functions: list[Function]
    static_vars: list[tacky.Static_Variable]

    @staticmethod
    def from_tacky(prog: tacky.Program):
        return Program(
            functions=[
                Function.from_tacky(function_def) for function_def in prog.function_defs
            ],
            static_vars=prog.static_vars,
        )

    def to_assembly(self) -> list[str]:
        res = ["\n".join(f.to_assembly()) for f in self.functions]
        res.append("\n".join(static_var_to_assembly(var) for var in self.static_vars))
        res.append('.section .note.GNU-stack,"",@progbits')
        return res

    @t.override
    def __str__(self):
        return "\n".join(map(str, self.static_vars + self.functions))


type Get_Val = "t.Callable[[tacky.Value | Pseudo], Operand]"


class Function(BaseModel):
    name: str
    is_global: bool
    instructions: "list[Instruction]"

    @t.override
    def __str__(self):
        start = pf.indent(
            dedent(
                f"""
                    (function
                      ('name {self.name})
                      ('instructions 
                """
            )
        )
        with pf.set_context(dt.INDENT_LEVEL, dt.INDENT_LEVEL.get() + 2):
            body = pf.indent("\n".join(repr(b) for b in self.instructions))

        return f"{start}{body})"

    @staticmethod
    def from_tacky(func: tacky.Function_Definition):
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

        def get_val(value: tacky.Value | Pseudo):
            match value:
                case parser.Constant(root=val):
                    return Imm(root=val)
                case tacky.Var(name=name):
                    if value.is_static():
                        return Data(root=name)

                    return Stack(root=get_stack(name))
                    # return Pseudo(root=name)
                case Pseudo(root=name):
                    return Stack(root=get_stack(name))
                    # return value

        for index in reversed(range(len(func.params))):
            arg_source = _get_system_v_call_convention(index)
            param_name = func.params[index][0].name
            if isinstance(arg_source, Stack):
                stack[param_name] = arg_source.root
            else:
                instructions.append(
                    Mov(
                        src=arg_source,
                        dest=get_val(Pseudo(root=func.params[index][0].name)),
                    )
                )

        for inst in func.instructions:
            match inst:
                case tacky.Func_Call():
                    instructions.extend(Call.from_ast(inst, get_val))
                case tacky.Return(root=value):
                    src = get_val(value) if value else Imm(root=0)
                    instructions.extend([Mov(src=src, dest=Reg(root="A")), Return()])

                case tacky.Unary():
                    instructions.extend(Unary.from_tacky(inst, get_val))

                case tacky.BinaryOp():
                    instructions.extend(Binary.from_tacky(inst, get_val))

                case tacky.Copy(src=src, dest=dest):
                    instructions.extend(Mov.new(get_val(src), get_val(dest)))

                case tacky.JumpIfZero(target=target, condition=condition):
                    label = target if isinstance(target, str) else target.identifier
                    instructions.extend(
                        (
                            Cmp(lhs=Imm(root=0), rhs=get_val(condition)),
                            JmpCC(cond="e", label=label),
                        )
                    )
                case tacky.JumpIfNotZero(target=target, condition=condition):
                    label = target if isinstance(target, str) else target.identifier

                    instructions.extend(
                        (
                            Cmp(lhs=Imm(root=0), rhs=get_val(condition)),
                            JmpCC(cond="ne", label=label),
                        )
                    )

                case tacky.Jump(target=target):
                    label = target if isinstance(target, str) else target.identifier
                    instructions.append(Jmp(root=label))

                case tacky.Label(identifier=identifier):
                    instructions.append(Label(root=identifier))
                    pass

        # TODO: A PASS HERE THAT CONVERTS FROM PSEUDO TO REGISTERS/STACK

        stack_allocation.root = stack_pointer - (stack_pointer % 16)
        return Function(
            name=func.name, instructions=instructions, is_global=func.is_global
        )

    def to_assembly(self) -> list[str]:
        # Weird - the book says to _always_ add a `.text` before every function definition
        res = [".text"]
        if self.is_global:
            res.append(f".globl\t{self.name}")

        res.extend(
            (
                f".type\t{self.name}, @function",
                f"{self.name}:",
                "\tpushq %rbp",
                "\tmovq %rsp, %rbp",
            )
        )
        res.extend(
            f"\t{'\n\t'.join(i.to_assembly().split('\n'))}" for i in self.instructions
        )

        return res


class Mov(BaseModel):
    src: Operand
    dest: Operand

    @staticmethod
    def new(src: Operand, dest: Operand) -> list[Mov]:
        if isinstance(src, (Stack, Data)) and isinstance(dest, (Stack, Data)):
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

    def to_assembly(self, type: dt.x64.Operation_Size = "l") -> str:
        # In the future - the type will be inferred according to the src/dest
        return f"mov{type} {self.src.to_assembly()}, {self.dest.to_assembly()}"


class Unary(BaseModel):
    op: tacky.Simple_Unary
    operand: Operand

    def to_assembly(self) -> str:
        match self.op:
            case "COMPLEMENT":
                return f"notl {self.operand.to_assembly()}"
            case "MINUS":
                return f"negl {self.operand.to_assembly()}"

    @staticmethod
    def from_tacky(arg: tacky.Unary, get_val: Get_Val) -> tuple[Instruction, ...]:
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
                    f"{ass_op} {self.src.to_assembly()}, {scratch.to_assembly()}\n"
                    f"{after.to_assembly()}"
                )
            case "PLUS" | "MINUS" | "ASTERISK" | "LEFT_SHIFT" | "RIGHT_SHIFT", _, Imm():
                raise ValueError(
                    "Bad assembly! Destination can't be a constant! It holds the result"
                )
            case "LEFT_SHIFT" | "RIGHT_SHIFT", Reg() | Stack(), dest:
                # TODO(Joaquim): See if we're using the C register and store it on the stack.
                # This nerd clobbers the C register, which is sad!
                # Left and right shift have a special rule
                # From the manual: https://www.felixcloutier.com/x86/sal:sar:shl:shr
                # > The destination operand can be a register or a memory
                # > location. The count operand can be an immediate value or
                # > the CL register
                # The source must be either a constant, or on the special %CL register
                scratch = Reg.get_scratch("C", 8)
                pre = Mov(src=self.src, dest=scratch)
                return (
                    # Said special `cl` register must be moved with `movb`?????
                    # Apparently the `CL` is a byte-sized register
                    # So we must move a bite
                    f"{pre.to_assembly('b')}\n"
                    f"{ass_op} {scratch.to_assembly()}, {dest.to_assembly()}\n"
                )
            case _, Stack() | Data(), Stack() | Data():
                scratch = Reg.get_scratch()
                pre = Mov(src=self.src, dest=scratch)
                return (
                    f"{pre.to_assembly()}\n"
                    f"{ass_op} {scratch.to_assembly()}, {self.dest.to_assembly()}"
                )

            case _:
                return f"{ass_op} {self.src.to_assembly()}, {self.dest.to_assembly()}"

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
                    Mov(src=src1, dest=Reg(root="A")),
                    Cdq(),
                    Idiv(root=src2),
                    Mov(
                        src=Reg(root="A" if inst.operation == "FORWARD_SLASH" else "D"),
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
            case (Stack() | Data(), Stack() | Data()):
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

        res.append(f"cmpl {source.to_assembly()}, {dest.to_assembly()}")
        return "\n".join(res)


class Jmp(BaseModel):
    root: dt.Identifier

    def to_assembly(self) -> str:
        return f"jmp {self.root}"


class JmpCC(BaseModel):
    label: dt.Identifier
    cond: Cond_Code

    def to_assembly(self) -> str:
        return f"j{self.cond} {self.label}"


class SetCC(BaseModel):
    operand: Stack | Reg
    cond: Cond_Code

    def to_assembly(self) -> str:
        return f"set{self.cond} {_get_8_bit(self.operand).to_assembly()}"


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
                    f"idivl {scratch.to_assembly()}"
                )
            case _:
                return f"idivl {self.root.to_assembly()}"


class Cdq(BaseModel):
    def to_assembly(self) -> str:
        return "cdq"


class AllocateStack(BaseModel):
    root: int = 0

    def to_assembly(self) -> str:
        # assert self.root % 16 == 0, "Not 16-byte aligned!!!"
        if dt.USE_ONLY_RBP.get():
            return f"subq ${abs(self.root)}, %rbp"
        return f"subq ${abs(self.root)}, %rsp"


class DeAllocateStack(RootModel[dt.Positive_Int]):
    def to_assembly(self) -> str:
        if dt.USE_ONLY_RBP.get():
            return f"addq ${abs(self.root)}, %rbp"
        return f"addq ${abs(self.root)}, %rsp"


class Push(BaseModel):
    operand: Operand

    def to_assembly(self) -> str:
        return f"pushq {self.operand.to_assembly()}"


class Call(BaseModel):
    name: tacky.Valid_Identifier

    def to_assembly(self) -> str:
        is_external = SYMBOL_TABLE.get().is_external(self.name)
        return f"call {self.name}{'@PLT' if is_external else ''}"

    @staticmethod
    def from_ast(call: tacky.Func_Call, get_val: Get_Val) -> list[Instruction]:
        instructions: list[Instruction] = []
        args = len(call.args)
        if args > dt.x64.NUMBER_OF_REGISTER_ARGUMENTS:
            args_in_stack = args - dt.x64.NUMBER_OF_REGISTER_ARGUMENTS
        else:
            args_in_stack = 0
        args_in_register = args - args_in_stack
        stack_padding = 0
        if args_in_stack and args_in_stack % 2:
            stack_padding = 8
            # For _REASONS_ the stack must be 16-byte aligned If the number of
            # arguments in the stack is odd, then we're gucci
            # Since we can only push to the stack using 64 bits, an even number
            # of make 16 bytes exactly.
            instructions.append(AllocateStack(root=stack_padding))

        for index in range(args_in_register):
            val = get_val(call.args[index])
            instructions.append(Mov(src=val, dest=_get_system_v_call_convention(index)))

        for index in reversed(
            range(
                dt.x64.NUMBER_OF_REGISTER_ARGUMENTS,
                dt.x64.NUMBER_OF_REGISTER_ARGUMENTS + args_in_stack,
            )
        ):
            val = get_val(call.args[index])
            match val:
                case Reg(root=root):
                    # Ensure we're pushing
                    # only 64 bits
                    instructions.append(Push(operand=Reg(root=root, size=64)))
                case Imm():
                    instructions.append(Push(operand=val))
                case Stack() | Data():
                    # If it's in memory we must first move it to `A` and then push that
                    # This...I don't understand - I suppose that it's for when we use memory in general
                    # instead of just "PUT EVERYTHING ON STACK"
                    accumulator = Reg(root="A", size=64)
                    instructions.extend(
                        (Mov(src=val, dest=Reg(root="A")), Push(operand=accumulator))
                    )
                case Pseudo():
                    raise ValueError("Nope!")
        # Finally - having set all of the little arguments, we can call the function
        instructions.append(Call(name=call.name))
        # Now we must adjust the stack pointer
        bytes_to_remove = 8 * args_in_stack + stack_padding
        if bytes_to_remove:
            instructions.append(DeAllocateStack(bytes_to_remove))

        instructions.append(Mov(src=Reg(root="A"), dest=get_val(call.dest)))
        return instructions


class Return(BaseModel):
    def to_assembly(self) -> str:
        return "\n".join(
            [
                "" if dt.USE_ONLY_RBP.get() else "movq %rbp, %rsp",
                "popq	%rbp",
                "ret",
            ]
        )


type Operand = Imm | Reg | Stack | Data | Pseudo
# Pseudo are replaced
# type AnyOperand = Operand | Pseudo


class Imm(BaseModel):
    root: int

    def to_assembly(self) -> str:
        return f"${self.root}"


# fmt: on
OLDEST_SCHOOL_REGISTERS = t.cast(
    frozenset[dt.Oldest_School_Registers],
    pf.get_literal_vals(dt.Oldest_School_Registers),
)

OLD_SCHOOL_REGISTERS = t.cast(
    frozenset[dt.Old_School_Registers], pf.get_literal_vals(dt.Old_School_Registers)
)


NEW_SCHOOL_REGISTERS = t.cast(
    frozenset[dt.New_School_Registers], pf.get_literal_vals(dt.New_School_Registers)
)


class Reg(BaseModel):
    root: dt.x64.Register
    size: dt.x64.Bit_Size = 32

    @staticmethod
    def get_scratch(
        which: t.Literal["R10", "R11", "C", "D"] = "R10", size: dt.x64.Bit_Size = 32
    ):
        return Reg(root=which, size=size)

    def to_assembly(self) -> str:
        if self.root in OLDEST_SCHOOL_REGISTERS:
            match self.size:
                case 64:
                    return f"%r{self.root.lower()}x"
                case 32:
                    # E is for `Extented`
                    return f"%e{self.root.lower()}x"
                case 16:
                    return f"%{self.root.lower()}x"
                case 8:
                    # L is for `lower` 8 bits of a register
                    return f"%{self.root.lower()}l"
        if self.root in OLD_SCHOOL_REGISTERS:
            match self.size:
                case 64:
                    # THIS IS WRONG! THIS IS ONLY FOR THE OLDEST SCHOOL ONES
                    # MAKES A MESS OF DI/SI/ETC
                    return f"%r{self.root.lower()}"
                case 32:
                    # E is for `Extented`
                    return f"%e{self.root.lower()}"
                case 16:
                    return f"%{self.root.lower()}"
                case 8:
                    # L is for `lower` 8 bits of a register
                    return f"%{self.root.lower()}l"
        match self.size:
            case 64:
                return f"%{self.root.lower()}"
            case 32:
                # d for double-WORD
                return f"%{self.root.lower()}d"
            case 16:
                # w is for a WORD (two bytes)
                return f"%{self.root.lower()}w"
            case 8:
                # b for byte
                return f"%{self.root.lower()}b"

    def is_callee_safe(self):
        """
        These are the only registers that _MUST_ not be changed by the child.
        If the child touches them, then they must be set back

        """
        return self.root in ("B", "BP", *(f"R{i}" for i in range(12, 16)))


class Pseudo(BaseModel):
    """
    I fucked up.

    All the way back in chapter2 the author mentions that I should convert all
    `tacky.Vars` into `pseudo-registers` and that later on there's another
    compiler-pass that replaces all `Pseudo` registers
    with either real-registers or some items on the stack.

    I did NOT do this at all, I got clever and now I've been bitten in the ass.
    """

    root: str

    def to_assembly(self) -> t.Never:
        raise NotImplementedError("This nerd should not be here yo!")


class Data(BaseModel):
    root: tacky.Valid_Identifier

    def to_assembly(self):
        return f"{self.root}(%rip)"


class Stack(BaseModel):
    root: int

    def to_assembly(self) -> str:
        return f"{self.root}(%rbp)"


class Ass(RootModel[str]):
    pass


def static_var_to_assembly(var: tacky.Static_Variable):
    global_directive = f".globl {var.name}" if var.is_global else ""
    section, actual_data = (
        (".bss", ".zero 4") if var.init == 0 else (".data", f".long {var.init}")
    )
    text = f"""\
	{global_directive} 
	{section}
	.align 4
{var.name}:
	{actual_data}"""

    return dedent(text)


def _get_8_bit(operand: Stack | Reg):
    match operand:
        case Stack():
            return operand
        case Reg(root=root):
            return Reg(root=root, size=8)


def _get_system_v_call_convention(index: int):
    reg = dt.x64.from_arg_number.get(index)
    if reg is None:
        # They're already on the stack!
        # Thanks System V ABI
        # Stack[0] will always be the BASE
        # RBP + 16 bytes is always the 7th argument passed.
        # See `chapter11/README.md:196`
        # Note: when we add different CTypes I'll have to tweak this
        return Stack(root=16 + 8 * (index - 6))
    return Reg(root=reg)
