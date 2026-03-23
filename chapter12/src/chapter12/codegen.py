"""
TODO(Joaquim):

- Replace the `new` methods That kind of stuff should be done on the
  `to_assembly` pass!
- Consider one _FAT_ function. The huge match-case on the `parser/tacky` files
  appears to lead to less bugs. Even if it's "uglier"


New shit in underscore
```
program = Program(top_level*)
_assembly_type = Longword | Quadword_
top_level = Function(identifier name, bool global, instruction* instructions)
          | StaticVariable(identifier name, bool global, _int alignment, static_init init_)
instruction = Mov(_assembly_type_, operand src, operand dst)
            | _Movsx(operand src, operand dst)_
            | Unary(unary_operator, _assembly_type_, operand)
            | Binary(binary_operator, _assembly_type_, operand, operand)
            | Cmp(_assembly_type_, operand, operand)
            | Idiv(_assembly_type_, operand)
            | Cdq(_assembly_type_)
            | Jmp(identifier)
            | JmpCC(cond_code, identifier)
            | SetCC(cond_code, operand)
            | Label(identifier)
            | Push(operand)
            | Call(identifier)
            | Ret

unary_operator = Neg | Not
binary_operator = Add | Sub | Mult
operand = Imm(int) | Reg(reg) | Pseudo(identifier) | Stack(int) | Data(identifier)
cond_code = E | NE | G | GE | L | LE
reg = AX | CX | DX | DI | SI | R8 | R9 | R10 | R11 | _SP_
```
"""

from textwrap import dedent
import typing as t

from pathlib import Path
from pydantic import BaseModel, RootModel, model_validator

from chapter12 import parser
from chapter12 import tacky
from chapter12.semantic_analysis import SYMBOL_TABLE, Symbol_Table
from shared import data_types as dt, pure_functions as pf


class BST:
    """
    BST -> Backend-Symbol-Table

    **THE BOOK** mentions how the assembly needs a different symbol-table.
    IMO...it was fine to use the old one
    But I suppose the book wants it this way for future chapters
    """

    data: t.ClassVar[dict[str, Symbol]] = {}

    type Symbol = AssObject | Func

    class AssObject(BaseModel):
        size: dt.x64.Bit_Size
        is_static: bool
        is_external: bool

    class Func(BaseModel):
        defined: bool
        is_external: bool

    @classmethod
    def init(cls):
        symbol_table = SYMBOL_TABLE.get()
        for name, symbol in symbol_table.data.items():
            is_external = symbol_table.is_external(name)
            match symbol:
                case Symbol_Table.Func(defined=defined):
                    cls.data[name] = cls.Func(defined=defined, is_external=is_external)
                case Symbol_Table.Static(type=type):
                    cls.data[name] = cls.AssObject(
                        size=type.get_size(), is_static=True, is_external=is_external
                    )
                case Symbol_Table.Local(type=type):
                    cls.data[name] = cls.AssObject(
                        size=type.get_size(), is_static=False, is_external=is_external
                    )

    @classmethod
    def get_size(cls, val: tacky.Value | str) -> dt.x64.Bit_Size:
        match val:
            case parser.Constant(ctype=ctype):
                return ctype.get_size()
            case tacky.Var(name=name) | str(name):
                # Will crash if it's a function
                # That's fine
                return cls.data[name].size  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]

    @classmethod
    def is_static(cls, name: str) -> bool:
        # Will crash if it's a function
        # That's fine
        return cls.data[name].is_static  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]


def parsed_to_assembly_construct(prog: tacky.Program):
    return Program.from_tacky(prog)


def to_assembly(filename: Path, prog: Program) -> Ass:
    """
    Since there's always just the one function...
    """
    resp: list[str] = [f'.file\t"{filename.name}"', *prog.to_assembly()]

    return Ass("\n".join(resp) + "\n")


type Instruction = (
    Comment
    | Mov
    | Unary
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
    | Movsx
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
    static_vars: list[Static_Variable]

    @staticmethod
    def from_tacky(prog: tacky.Program):
        BST.init()
        return Program(
            functions=[
                Function.from_tacky(function_def) for function_def in prog.function_defs
            ],
            static_vars=[Static_Variable.from_tacky(t) for t in prog.static_vars],
        )

    def to_assembly(self) -> list[str]:
        res = ["\n".join(f.to_assembly()) for f in self.functions]
        res.append("\n".join(static_var_to_assembly(var) for var in self.static_vars))
        res.append('.section .note.GNU-stack,"",@progbits')
        return res

    @t.override
    def __str__(self):
        return "\n".join(map(str, self.static_vars + self.functions))


class Static_Variable(tacky.Static_Variable):
    alignment: int

    @staticmethod
    def from_tacky(tacky: tacky.Static_Variable):
        return Static_Variable(
            name=tacky.name,
            is_global=tacky.is_global,
            init=tacky.init,
            type=tacky.type,
            alignment=(4 if tacky.type.root == "int" else 8),
        )


type Get_Val = "t.Callable[[tacky.Value | Pseudo], Operand]"


class Sized(BaseModel):
    size: dt.x64.Bit_Size

    def assembly_type(self):
        return dt.x64.from_bit_size[self.size]


class Function(BaseModel):
    name: str
    is_global: bool
    instructions: list[Instruction]

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
        stack_allocation = allocate_stack(0)

        if t.TYPE_CHECKING:
            assert isinstance(stack_allocation.src, Imm)

        include_comments = dt.DEBUG.get()
        stack_pointer = 0
        stack: dict[str, int] = {}

        instructions: list[Instruction] = (
            [Comment(root=stack), stack_allocation]
            if include_comments
            else [stack_allocation]
        )

        def get_stack(name: str):
            nonlocal stack_pointer
            if name in stack:
                return stack[name]
            size = BST.get_size(name)

            if size == 32:
                # bump the stack!
                stack_pointer -= 4
            else:
                stack_pointer -= 8
                # Alignment - get close to the nearest 64 bits
                stack_pointer -= stack_pointer % 8
            stack[name] = stack_pointer
            return stack_pointer

        # def pseudo_to_operand(pseudo: Pseudo):
        #     return Stack(root=get_stack(pseudo.root))  # noqa: ERA001

        def get_val(value: tacky.Value | Pseudo):
            match value:
                case parser.Constant(root=val):
                    return Imm(root=val)
                case tacky.Var(name=name):
                    if BST.is_static(name):
                        return Data(root=name)
                    # return Pseudo(root=name, to_operand=pseudo_to_operand)  # noqa: ERA001
                    return Stack(root=get_stack(name))
                case Pseudo(root=name):
                    # return Pseudo(root=name, to_operand=pseudo_to_operand)  # noqa: ERA001
                    return Stack(root=get_stack(name))

        for index in reversed(range(len(func.params))):
            param_name = func.params[index][0].name
            arg_size = func.params[index][1].get_size()
            arg_source = _get_system_v_call_convention(index, arg_size)
            if isinstance(arg_source, Stack):
                stack[param_name] = arg_source.root
            else:
                instructions.extend(
                    Mov.new(
                        size=arg_size,
                        src=arg_source,
                        dest=get_val(Pseudo(root=func.params[index][0].name)),
                        # dest=Pseudo(root=func.params[index][0].name, to_operand=pseudo_to_operand),  # noqa: ERA001
                    )
                )

        for inst in func.instructions:
            if include_comments:
                instructions.append(Comment(root=str(inst)))
            match inst:
                case tacky.Truncate(src=src, dest=dest):
                    instructions.extend(
                        Mov.new(
                            size=32,
                            src=get_val(src),
                            dest=get_val(dest),
                        )
                    )
                case tacky.SignExtend(src=src, dest=dest):
                    instructions.extend(Movsx.new(src=get_val(src), dest=get_val(dest)))
                case tacky.Func_Call():
                    instructions.extend(Call.from_ast(inst, get_val))
                case tacky.Return(root=value):
                    src = get_val(value) if value else Imm(root=0)
                    size = BST.get_size(value) if value else 32
                    instructions.extend(
                        [
                            *Mov.new(size=size, src=src, dest=Reg(root="A", size=size)),
                            Return(),
                        ]
                    )

                case tacky.Unary():
                    instructions.extend(Unary.from_tacky(inst, get_val))

                case tacky.BinaryOp():
                    instructions.extend(Binary.from_tacky(inst, get_val))

                case tacky.Copy(src=src, dest=dest):
                    instructions.extend(
                        Mov.new(
                            BST.get_size(src),
                            get_val(src),
                            get_val(dest),
                        )
                    )

                case tacky.JumpIfZero(target=target, condition=condition):
                    label = target if isinstance(target, str) else target.identifier
                    size = BST.get_size(condition)
                    instructions.extend(
                        (
                            Cmp(size=size, lhs=Imm(root=0), rhs=get_val(condition)),
                            JmpCC(cond="e", label=label),
                        )
                    )
                case tacky.JumpIfNotZero(target=target, condition=condition):
                    label = target if isinstance(target, str) else target.identifier
                    size = BST.get_size(condition)

                    instructions.extend(
                        (
                            Cmp(size=size, lhs=Imm(root=0), rhs=get_val(condition)),
                            JmpCC(cond="ne", label=label),
                        )
                    )

                case tacky.Jump(target=target):
                    label = target if isinstance(target, str) else target.identifier
                    instructions.append(Jmp(root=label))

                case tacky.Label(identifier=identifier):
                    instructions.append(Label(root=identifier))

        # Finally - we adjust the original instruction to align everything to 16-bytes
        # AND TO MAKE IT POSITIVE
        stack_allocation.src.root = abs(stack_pointer - (stack_pointer % 16))
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

        if dt.DEBUG.get():
            for i in self.instructions:
                temp = []
                if not isinstance(i, Comment):
                    temp = [f"# {i!r}"]
                temp.extend(i.to_assembly().split("\n"))

                res.append(f"\t{'\n\t'.join(temp)}")
        else:
            res.extend(
                f"\t{'\n\t'.join(i.to_assembly().split('\n'))}"
                for i in self.instructions
            )

        return res


class Comment(BaseModel):
    root: object

    def to_assembly(self) -> str:
        return f"# TACKY {self.root!s}"


class Mov(Sized):
    src: Operand
    dest: Operand

    @staticmethod
    def new(size: dt.x64.Bit_Size, src: Operand, dest: Operand) -> list[Mov]:
        """
        TODO(Joaquim): Get rid of this and do it only at the `to_assembly` level
        """
        match src, dest:
            case Stack() | Data(), Stack() | Data():
                # It's illegal to mov from one mem-address into another
                # So we need to move to a strach register
                scratch = Reg.get_scratch(size=size)
                return [
                    Mov(size=size, src=src, dest=scratch),
                    Mov(size=size, src=scratch, dest=dest),
                ]

            case Imm(root=root), _ if root >= dt.x64.max[32]:
                if size == 32:
                    # we have to truncate the value
                    src = src.truncate()
                    return [Mov(size=size, src=src, dest=dest)]
                # Large nerds must first go into a register
                scratch = Reg.get_scratch(size=size)
                return [
                    Mov(size=size, src=src, dest=scratch),
                    Mov(size=size, src=scratch, dest=dest),
                ]

            case _:
                # just one mov is fine
                return [Mov(size=size, src=src, dest=dest)]

    @model_validator(mode="after")
    def assert_no_illegal(self):
        match (self.src, self.dest):
            case (Stack() | Data(), Stack() | Data()):
                raise ValueError("You can't move from one memory address to another!")
            case Imm(root=root), Stack() | Data() if root >= dt.x64.max[32]:
                raise ValueError("Nope!")
            case (Imm(), Imm()):
                raise ValueError("You can't move one constant on top of another!")
            case _:
                return self

    def to_assembly(self) -> str:
        return f"mov{self.assembly_type()} {self.src.to_assembly()}, {self.dest.to_assembly()}"


class Movsx(BaseModel):
    src: Operand
    dest: Operand

    @staticmethod
    def new(src: Operand, dest: Operand) -> list[Movsx | Mov]:
        both_are_memory = all(isinstance(d, (Stack, Data)) for d in (src, dest))
        source_is_imm = isinstance(src, Imm)
        if both_are_memory or source_is_imm:
            # Just like a normal mov, we have to do some tweaking
            return [
                *Mov.new(size=32, src=src, dest=Reg(root="R10", size=32)),
                Movsx(src=Reg(root="R10", size=32), dest=Reg(root="R11", size=64)),
                Mov(size=64, src=Reg(root="R11", size=64), dest=dest),
            ]
        return [Movsx(src=src, dest=dest)]

    @model_validator(mode="after")
    def assert_no_illegal(self):
        match (self.src, self.dest):
            case (Stack(), Stack()):
                raise ValueError("You can't move from one memory address to another!")
            case (Imm(), Imm()):
                raise ValueError("You can't move one constant on top of another!")
            case _:
                return self

    def to_assembly(self) -> str:
        return f"movslq {self.src.to_assembly()}, {self.dest.to_assembly()}"


class Unary(Sized):
    op: tacky.Simple_Unary
    operand: Operand

    def to_assembly(self) -> str:
        match self.op:
            case "COMPLEMENT":
                return f"not{self.assembly_type()} {self.operand.to_assembly()}"
            case "MINUS":
                return f"neg{self.assembly_type()} {self.operand.to_assembly()}"

    @staticmethod
    def from_tacky(arg: tacky.Unary, get_val: Get_Val) -> tuple[Instruction, ...]:
        match arg:
            case tacky.Unary(
                operation="NOT",
                source=source,
                destination=destination,
            ):
                dst = get_val(destination)
                size = BST.get_size(source)
                return (
                    Cmp(size=size, lhs=Imm(root=0), rhs=get_val(source)),
                    Mov(size=size, src=Imm(root=0), dest=dst),
                    SetCC(cond="e", operand=dst),  # pyright: ignore[reportArgumentType]
                )

            case tacky.Unary(
                operation=operation,
                source=source,
                destination=destination,
            ):
                src = get_val(source)
                dest = get_val(destination)
                size = BST.get_size(source)
                return (
                    *Mov.new(size=size, src=src, dest=dest),
                    Unary(
                        size=size,
                        op=operation,  # pyright: ignore[reportArgumentType]
                        operand=dest,
                    ),
                )


class Binary(Sized):
    op: parser.Simple_Binary
    src: Operand
    dest: Operand

    def to_assembly(self) -> str:
        def match_op(op: parser.Simple_Binary):
            match op:
                case "MINUS":
                    return "sub"
                case "PLUS":
                    return "add"
                case "ASTERISK":
                    return "imul"
                case "LEFT_SHIFT":
                    return "sal"
                case "RIGHT_SHIFT":
                    return "sar"
                case "AMPERSAND":
                    return "and"
                case "PIPE":
                    return "or"
                case "CARRET":
                    return "xor"

        ass_op = f"{match_op(self.op)}{self.assembly_type()}"

        match (self.op, self.src, self.dest):
            case "PLUS" | "MINUS" | "ASTERISK" | "LEFT_SHIFT" | "RIGHT_SHIFT", _, Imm():
                raise ValueError(
                    "Bad assembly! Destination can't be a constant! It holds the result"
                )

            case "ASTERISK", _, Stack() | Data():
                scratch = Reg.get_scratch("R11", size=self.size)
                pre = Mov.new(src=self.dest, dest=scratch, size=self.size)
                after = Mov.new(src=scratch, dest=self.dest, size=self.size)
                return (
                    f"{'\n'.join(p.to_assembly() for p in pre)}\n"
                    f"{Binary(op=self.op, src=self.src, dest=scratch, size=self.size).to_assembly()}\n"
                    f"{'\n'.join(a.to_assembly() for a in after)}"
                )

            case "LEFT_SHIFT" | "RIGHT_SHIFT", Reg() | Stack(), dest:
                # Left and right shift have a special rule
                # From the manual: https://www.felixcloutier.com/x86/sal:sar:shl:shr
                # > The destination operand can be a register or a memory
                # > location. The count operand can be an immediate value or
                # > the CL register
                # The source must be either a constant, or on the special %CL register
                scratch = Reg.get_scratch("C", 8)
                pre = Mov(size=8, src=self.src, dest=scratch)
                return (
                    f"{pre.to_assembly()}\n"
                    f"{ass_op} {scratch.to_assembly()}, {dest.to_assembly()}\n"
                )
            case _, Stack() | Data(), Stack() | Data():
                scratch = Reg.get_scratch(size=self.size)
                pre = Mov(size=self.size, src=self.src, dest=scratch)
                return (
                    f"{pre.to_assembly()}\n"
                    f"{ass_op} {scratch.to_assembly()}, {self.dest.to_assembly()}"
                )

            case _, Imm(root=root), __:
                if root < dt.x64.max[32]:
                    return (
                        f"{ass_op} {self.src.to_assembly()}, {self.dest.to_assembly()}"
                    )
                if self.size == 32:
                    # truncate it
                    src = self.src.truncate()
                    return f"{ass_op} {src.to_assembly()}, {self.dest.to_assembly()}"
                # shit! We have to first mov them
                scratch = Reg.get_scratch(size=self.size)
                pre = Mov(size=self.size, src=self.src, dest=scratch)
                return (
                    f"{pre.to_assembly()}\n"
                    f"{ass_op} {scratch.to_assembly()}, {self.dest.to_assembly()}"
                )

            case _:
                return f"{ass_op} {self.src.to_assembly()}, {self.dest.to_assembly()}"

    @staticmethod
    def from_tacky(inst: tacky.BinaryOp, get_val: Get_Val) -> tuple[Instruction, ...]:
        src1 = get_val(inst.src1)
        src2 = get_val(inst.src2)
        dest = get_val(inst.dest)

        size = BST.get_size(inst.src1)
        match inst.operation:
            case "FORWARD_SLASH" | "PERCENT":
                # Division/remainder - are a bit of an ass
                # `idiv` slaps the result in `A` and the remainder in `D`
                return (
                    Mov(size=size, src=src1, dest=Reg(root="A", size=size)),
                    Cdq(size=size),
                    Idiv(size=size, root=src2),
                    Mov(
                        size=size,
                        src=Reg(
                            root="A" if inst.operation == "FORWARD_SLASH" else "D",
                            size=size,
                        ),
                        dest=dest,
                    ),
                )

            case "LE" | "LT" | "GT" | "GE" | "==" | "!=":
                return (
                    Cmp(size=size, lhs=src2, rhs=src1),
                    # The actual dest will be an int
                    Mov(size=32, src=Imm(root=0), dest=dest),
                    SetCC(
                        cond=map_relational_to_cond_code(inst.operation),
                        operand=dest,  # pyright: ignore[reportArgumentType]
                    ),
                )

            case _arrithmetic:
                return (
                    *Mov.new(size=size, src=src1, dest=dest),
                    Binary(
                        size=size,
                        op=inst.operation,  # pyright: ignore[reportArgumentType]
                        src=src2,
                        dest=dest,
                    ),
                )
        raise ValueError("unreachable")  # pyright: ignore[reportUnreachable]


class Cmp(Sized):
    lhs: Operand
    rhs: Operand

    def to_assembly(self) -> str:
        match self.lhs, self.rhs:
            case (Stack() | Data(), Stack() | Data()):
                scratch = Reg.get_scratch(size=self.size)
                intermediate = Mov(src=self.lhs, dest=scratch, size=self.size)
                return (
                    f"{intermediate.to_assembly()}\n"
                    f"cmp{self.assembly_type()} {scratch.to_assembly()}, {self.rhs.to_assembly()}"
                )

            case (_, Imm()):
                # The destination can never be an Immediate
                # (This seems weird, shouldn't I just switch them?)
                dest = Reg.get_scratch(size=self.size)
                intermediate = Mov(src=self.rhs, dest=dest, size=self.size)
                if isinstance(self.lhs, Imm) and self.lhs.root >= dt.x64.max[32]:
                    # ....dammmmit!
                    another_scratch = Reg.get_scratch(which="R11", size=self.size)
                    pre = Mov(size=self.size, src=self.lhs, dest=another_scratch)
                    return (
                        f"{intermediate.to_assembly()}\n"
                        f"{pre.to_assembly()}\n"
                        f"cmp{self.assembly_type()} {another_scratch.to_assembly()}, {dest.to_assembly()}"
                    )
                return (
                    f"{intermediate.to_assembly()}\n"
                    f"cmp{self.assembly_type()} {self.lhs.to_assembly()}, {dest.to_assembly()}"
                )

            case Imm(root=root), _:
                if root >= dt.x64.max[32] and self.size == 64:
                    # shit! We have to first mov them
                    scratch = Reg.get_scratch(size=self.size)
                    pre = Mov(size=self.size, src=self.lhs, dest=scratch)
                    return (
                        f"{pre.to_assembly()}\n"
                        f"cmp{self.assembly_type()} {scratch.to_assembly()}, {self.rhs.to_assembly()}"
                    )

            case _:
                pass

        return f"cmp{self.assembly_type()} {self.lhs.to_assembly()}, {self.rhs.to_assembly()}"


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


class Idiv(Sized):
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
                scratch = Reg.get_scratch(size=self.size)
                return (
                    f"{Mov(size=self.size, src=self.root, dest=scratch).to_assembly()}\n"
                    f"idiv{self.assembly_type()} {scratch.to_assembly()}"
                )
            case _:
                return f"idiv{self.assembly_type()} {self.root.to_assembly()}"


class Cdq(Sized):
    def to_assembly(self) -> str:
        """
        This mnemonic is different because (???)
        """
        match self.size:
            case 64:
                return "cqo"
            case 32:
                return "cdq"
            case _:
                raise ValueError("no idea man")


def allocate_stack(bytes: int):
    return Binary(
        size=64, op="MINUS", src=Imm(root=abs(bytes)), dest=Reg(root="SP", size=64)
    )


def de_allocate_stack(bytes: int):
    return Binary(
        size=64, op="PLUS", src=Imm(root=abs(bytes)), dest=Reg(root="SP", size=64)
    )


class Push(BaseModel):
    operand: Operand

    def to_assembly(self) -> str:
        match self.operand:
            case Imm(root=root) if root >= dt.x64.max[32]:
                scratch = Reg.get_scratch(size=64)
                pre = Mov(size=64, src=self.operand, dest=scratch)
                return f"{pre.to_assembly()}\npushq {scratch.to_assembly()}"
            case _:
                return f"pushq {self.operand.to_assembly()}"


class Call(BaseModel):
    name: tacky.Valid_Identifier

    def to_assembly(self) -> str:
        is_external = BST.data[self.name].is_external
        return f"call {self.name}{'@PLT' if is_external else ''}"

    @staticmethod
    def from_ast(call: tacky.Func_Call, get_val: Get_Val) -> list[Instruction]:
        instructions: list[Instruction] = []
        args = len(call.args)
        # There's a maximum number of arguments that go on registers
        args_in_register = min(args, dt.x64.NUMBER_OF_REGISTER_ARGUMENTS)
        args_in_stack = args - args_in_register

        stack_padding = 0

        if args_in_stack % 2:
            stack_padding = 8
            # For _REASONS_ the stack must be 16-byte aligned If the number of
            # arguments in the stack is even, then we're gucci.
            # Since we can only push to the stack using 64 bits, an even number
            # makes 16 bytes exactly.
            # example:
            # args_on_stack = { 64b } # OOPS, we're missing 8
            # args_on_stack = { 64b, 64b } # All good! (64 + 64) / 8 % 16 == 0
            # args_on_stack = { 64b, 64b, 64b } # OOPS, we're missing 8 again.
            instructions.append(allocate_stack(stack_padding))

        for index in range(args_in_register):
            val = get_val(call.args[index])
            size = BST.get_size(call.args[index])
            instructions.append(
                Mov(size=size, src=val, dest=_get_system_v_call_convention(index, size))
            )

        for index in reversed(
            range(
                dt.x64.NUMBER_OF_REGISTER_ARGUMENTS,
                dt.x64.NUMBER_OF_REGISTER_ARGUMENTS + args_in_stack,
            )
        ):
            current = call.args[index]
            val = get_val(current)
            size = BST.get_size(current)

            match val:
                case Pseudo():
                    # We shouldn't have reached this stage with a speudo register
                    raise ValueError("Nope!")
                case Reg(root=root):
                    # Ensure we're pushing
                    # only 64 bits
                    instructions.append(Push(operand=Reg(root=root, size=64)))
                case Imm():
                    instructions.append(Push(operand=val))
                case _ if size == 64:
                    # We can just push it! No problemo
                    instructions.append(Push(operand=val))
                case _:
                    # If it's in memory and NOT 64 bits then we must first move our 32 value
                    # into the A register
                    # Then we can push _that_ register over to the stack no problem
                    accumulator_small = Reg(root="A", size=32)
                    accumulator = Reg(root="A", size=64)

                    instructions.extend(
                        (
                            Mov(
                                size=32,
                                src=val,
                                dest=accumulator_small,
                            ),
                            Push(operand=accumulator),
                        )
                    )

        # Finally - having set all of the little arguments, we can call the function
        instructions.append(Call(name=call.name))
        # Now we must adjust the stack pointer
        bytes_to_remove = 8 * args_in_stack + stack_padding
        if bytes_to_remove:
            instructions.append(de_allocate_stack(bytes_to_remove))

        return_size = BST.get_size(call.dest)
        instructions.append(
            Mov(
                size=return_size,
                src=Reg(root="A", size=return_size),
                dest=get_val(call.dest),
            )
        )
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


class Imm(BaseModel):
    root: int

    def to_assembly(self) -> str:
        return f"${self.root}"

    def truncate(self, size: dt.x64.Bit_Size = 32):
        # Supposedly, we should be able to "just" do
        # root & 0xffffffff
        # But this doesn't seem correct for a number like
        # 4294967294
        # I mean, it _does_ in terms of binary, but python will
        # print it as a normal integer, since ints in python are infinite

        val = dt.x64.umax[size] + 1
        root = self.root - val * (self.root // val)
        if root >= dt.x64.max[size]:
            root -= dt.x64.umax[size]

        if root >= dt.x64.max[size]:
            raise ValueError("Programmer skill issue. Should be impossible")

        return Imm(root=root)


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
    size: dt.x64.Bit_Size

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
                    return f"%r{self.root.lower()}"
                case 32:
                    return f"%e{self.root.lower()}"
                case 16:
                    return f"%{self.root.lower()}"
                case 8:
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

    # Attempt to "fix" the issue
    # to_operand: t.Callable[[Pseudo], Stack | Data | Reg]  # noqa: ERA001

    def to_assembly(self) -> t.Never:
        # return self.to_operand(self).to_assembly()  # noqa: ERA001
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


def static_var_to_assembly(var: Static_Variable):
    global_directive = f".globl {var.name}" if var.is_global else ""

    match var.init.val, var.type.root:
        case 0, "int":
            section, actual_data = (".bss", ".zero 4")
        case 0, "long":
            section, actual_data = (".bss", ".zero 8")
        case int(), "int":
            section, actual_data = (".data", f".long {var.init.val}")
        case int(), "long":
            section, actual_data = (".data", f".quad {var.init.val}")
        case _:
            raise TypeError()

    text = f"""\
	{global_directive} 
	{section}
	.align {var.alignment}
{var.name}:
	{actual_data}"""

    return dedent(text)


def _get_8_bit(operand: Stack | Reg):
    match operand:
        case Stack():
            return operand
        case Reg(root=root):
            return Reg(root=root, size=8)


def _get_system_v_call_convention(index: int, size: dt.x64.Bit_Size):
    reg = dt.x64.from_arg_number.get(index)
    if reg is None:
        # They're already on the stack!
        # Thanks System V ABI
        # Stack[0] will always be the BASE
        # RBP + 16 bytes is always the 7th argument passed.
        # See `chapter12/README.md:196`
        # Note: when we add different CTypes I'll have to tweak this
        return Stack(root=16 + 8 * (index - 6))
    return Reg(root=reg, size=size)
