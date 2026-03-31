"""
TODO(Joaquim):

- Replace the `new` methods That kind of stuff should be done on the
  `to_assembly` pass!
- Consider one _FAT_ function. The huge match-case on the `parser/tacky` files
  appears to lead to less bugs. Even if it's "uglier"


New shit in underscore
```
program = Program(toplevel*)
assemblytype = Longword | Quadword
toplevel = Function(identifier name, bool global, instruction* instructions)
          | StaticVariable(identifier name, bool global, int alignment, staticinit init)
instruction = Mov(assemblytype, operand src, operand dst)
            | Movsx(operand src, operand dst)
            | _MovZeroExtend(operand src, operand dst)_
            | Unary(unaryoperator, assemblytype, operand)
            | Binary(binaryoperator, assemblytype, operand, operand)
            | Cmp(assemblytype, operand, operand)
            | Idiv(assemblytype, operand)
            | Div(assemblytype, operand)
            | Cdq(assemblytype)
            | Jmp(identifier)
            | JmpCC(condcode, identifier)
            | SetCC(condcode, operand)
            | Label(identifier)
            | Push(operand)
            | Call(identifier)
            | Ret

unaryoperator = Neg | Not
binaryoperator = Add | Sub | Mult
operand = Imm(int) | Reg(reg) | Pseudo(identifier) | Stack(int) | Data(identifier)
condcode = E | NE | G | GE | L | LE | A | AE | B | BE
reg = AX | CX | DX | DI | SI | R8 | R9 | R10 | R11 | SP
```
"""

from textwrap import dedent
import typing as t
from collections import abc

from pathlib import Path
from pydantic import BaseModel, Field, RootModel, model_validator

from chapter13 import parser, tacky, semantic_analysis
from chapter13.semantic_analysis import SYMBOL_TABLE, Symbol_Table
from shared import data_types as dt, pure_functions as pf

type Identifier_For_Assembly = t.Annotated[
    str, Field(pattern=rf"^[\._a-zA-Z]{dt.Identifier_Pattern}*$")
]
"""
Labels are allowed to start with a dot
"""


class BST:
    """
    BST -> Backend-Symbol-Table

    **THE BOOK** mentions how the assembly needs a different symbol-table.
    IMO...it was fine to use the old one
    But I suppose the book wants it this way for future chapters
    """

    data: t.ClassVar[dict[str, Symbol]] = {}
    seen_locals: t.ClassVar[dict[str, str]] = {}
    """
    Accepts a stringified number and returns the name of that object on the BST

    We do this stringification because -0.0 != 0.0 != 0
    Bit silly - but what can ya do
    """

    type Symbol = AssObject | Func

    class AssObject(BaseModel):
        type: parser.TrivialType
        is_static: bool
        is_external: bool
        is_constant: bool

    class Func(BaseModel):
        defined: bool
        is_external: bool

    @classmethod
    def init(cls):
        symbol_table = SYMBOL_TABLE.get()
        # Locals - as the name indicates - are _local_
        cls.seen_locals = {}
        for name, symbol in symbol_table.data.items():
            is_external = symbol_table.is_external(name)
            match symbol:
                case Symbol_Table.Func(defined=defined):
                    cls.data[name] = cls.Func(defined=defined, is_external=is_external)
                case Symbol_Table.Static(type=type):
                    cls.data[name] = cls.AssObject(
                        type=type,
                        is_static=True,
                        is_external=is_external,
                        is_constant=False,
                    )
                case Symbol_Table.Local(type=type):
                    cls.data[name] = cls.AssObject(
                        type=type,
                        is_static=False,
                        is_external=is_external,
                        is_constant=False,
                    )

    @classmethod
    def get_type(cls, val: tacky.Value | str):
        match val:
            case parser.Constant(ctype=ctype):
                return ctype
            case tacky.Var(name=name) | str(name):
                value = cls.data[name]
                assert isinstance(value, BST.AssObject)
                return value.type

    # TODO(Joaquim): Get rid of these one liner helper functions

    @classmethod
    def get_size(cls, val: tacky.Value | str) -> dt.x64.Bit_Size | t.Literal[128]:
        return cls.get_type(val).get_size()

    @classmethod
    def is_signed(cls, val: tacky.Value) -> bool:
        return cls.get_type(val).is_signed()

    @classmethod
    def is_double(cls, val: tacky.Value) -> bool:
        return cls.get_type(val).root == "double"

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
    | Div
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
    | Mov_Zero_Extend
    | CvtTSD2SI
    | CvtSI2SD
)
type Cond_Code = t.Literal["e", "ne", "g", "ge", "l", "le", "a", "ae", "b", "be"]
"""
Mnemonic:

    e -> equal
    ne -> not equal
    <x>e -> x or equal
    g -> greater
    l -> lower
    a -> above (for signed)
    b -> below
"""


def map_relational_to_cond_code(
    code: parser.Relational_Binary,
    *,
    is_signed: bool,
    is_double: bool,
) -> Cond_Code:
    # We use the `Below/Above` mnemonic if we're a double OR unsigned or a
    # pointer
    # ie: only use `lg` if we're int/long
    use_above_below = is_double or not is_signed
    match code, use_above_below:
        case "==", _:
            return "e"
        case "!=", _:
            return "ne"
        case "LE", False:
            return "le"
        case "LE", True:
            return "be"
        case "LT", False:
            return "l"
        case "LT", True:
            return "b"
        case "GT", False:
            return "g"
        case "GT", True:
            return "a"
        case "GE", False:
            return "ge"
        case "GE", True:
            return "ae"


class Program(BaseModel):
    functions: list[Function]
    static_vars: list[Static_Variable]

    @staticmethod
    def from_tacky(prog: tacky.Program):
        BST.init()
        static_vars = [Static_Variable.from_tacky(t) for t in prog.static_vars]
        functions = [
            Function.from_tacky(function_def, static_vars)
            for function_def in prog.function_defs
        ]
        return Program(
            functions=functions,
            static_vars=static_vars,
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
    is_constant: bool

    @model_validator(mode="after")
    def tweak_name(self):
        if self.is_constant and not self.name.startswith(".L_"):
            self.name = f".L_{self.name}"  # pyright: ignore[reportUnannotatedClassAttribute]
        return self

    @classmethod
    def from_tacky(cls, tacky: tacky.Static_Variable):
        return cls(
            name=tacky.name,
            is_global=tacky.is_global,
            init=tacky.init,
            type=tacky.type,
            alignment=(4 if tacky.type.root == "int" else 8),
            is_constant=False,
        )

    @classmethod
    def from_local(
        cls,
        const: parser.Constant,
        static_vars: list[Static_Variable],
        alignment: int | None = None,
    ):
        # We do this just so that we don't define some `.L_static` that equals zero all over
        # the place
        stringified = (
            hex(const.root) if isinstance(const.root, int) else const.root.hex()
        )

        if alignment is None:
            alignment = 4 if const.ctype.root == "int" else 8

        def res(name: str):
            return cls(
                name=name,
                is_global=False,
                init=semantic_analysis.StaticInit(val=const.root),
                type=const.ctype,
                alignment=alignment,
                is_constant=True,
            )

        if stringified in BST.seen_locals:
            return res(BST.seen_locals[stringified])

        # The book says that we don't need to do this `.L` trick yet
        # Instead it should be done in the actual `to_assembly` part
        # In my code it just works out better if we do it like this
        name = semantic_analysis.get_new_name(f"static_{stringified}_")
        BST.seen_locals[stringified] = name
        BST.data[name] = BST.AssObject(
            type=const.ctype,
            is_static=True,
            is_external=False,
            is_constant=True,
        )
        new_var = res(name)
        static_vars.append(new_var)
        return res(name)


type Get_Val = "t.Callable[[tacky.Value | Pseudo], Operand]"


class _Sized(BaseModel):
    size: dt.x64.Bit_Size | t.Literal[128]

    def assembly_type(self):
        if self.size < 128:
            size: dt.x64.Bit_Size = self.size  # pyright: ignore[reportAssignmentType]
            return dt.x64.from_bit_size[size]
        # This (shitty) compiler only does 64-bit floats
        # SD stands for `stacked-double`
        return "sd"


class _SrcDest(BaseModel):
    src: Operand
    dest: Operand


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
    def from_tacky(
        func: tacky.Function_Definition, static_variables: list[Static_Variable]
    ):
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

            if BST.get_size(name) == 32:
                # bump the stack!
                stack_pointer -= 4
            else:
                stack_pointer -= 8
                # Alignment - get close to the nearest 64 bits
                stack_pointer -= stack_pointer % 8

            stack[name] = stack_pointer

            return stack[name]

        # def pseudo_to_operand(pseudo: Pseudo):
        #     return Stack(root=get_stack(pseudo.root))  # noqa: ERA001

        def get_val(value: tacky.Value | Pseudo, *, enforce_static: bool = False):
            match value:
                case parser.Constant(root=val, ctype=ctype):
                    if ctype.root != "double" and not enforce_static:
                        return Imm(root=t.cast(int, val))
                    # A constant _can't_ be an immediate if it's a float!
                    # It _must_ be added to the `Data`
                    local_double = Static_Variable.from_local(value, static_variables)
                    return Data(root=local_double.name)
                case tacky.Var(name=name):
                    if BST.is_static(name):
                        return Data(root=pf.to_valid_c_name(name))
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
                instructions.append(
                    Mov(
                        size=arg_size,
                        src=arg_source,
                        dest=get_val(Pseudo(root=func.params[index][0].name)),
                    )
                )

        for inst in func.instructions:
            if include_comments:
                instructions.append(Comment(root=str(inst)))
            match inst:
                case tacky.IntToDouble(src=src, dest=dest):
                    instructions.append(
                        CvtSI2SD(
                            src=get_val(src, enforce_static=True),
                            dest=get_val(dest),
                            # type ignore because we _know_ it'll be smaller
                            # than 128
                            src_size=BST.get_size(src),  # pyright: ignore[reportArgumentType]
                        )
                    )
                case tacky.UIntToDouble(src=src, dest=dest):
                    size = BST.get_size(src)
                    if size == 32:
                        instructions.extend(
                            (
                                # If it's an int simply convert it into a long
                                Mov_Zero_Extend(
                                    src=get_val(src),
                                    dest=GeneralReg(root="R11", size=32),
                                ),
                                # And then do the thing
                                CvtSI2SD(
                                    src=GeneralReg(root="R11", size=64),
                                    dest=get_val(dest),
                                    # It _will_ be less than 128
                                    # because we don't do 128 ints
                                    src_size=64,
                                ),
                            )
                        )
                    else:
                        # Shit...
                        src_v = get_val(src)
                        dest_v = get_val(dest)
                        size = t.cast(t.Literal[64], size)
                        label_1 = Label(
                            root=semantic_analysis.get_new_name("out_of_range"),
                            local=True,
                        )
                        label_end = Label(
                            root=semantic_analysis.get_new_name("end"), local=True
                        )

                        scratch_1 = GeneralReg.get_scratch(size=64)
                        scratch_2 = GeneralReg.get_scratch(which="R11", size=64)

                        instructions.extend(
                            (
                                # if it's in range of what signed long can represent
                                # That's as simple as checking if the first bit is a 1
                                # (Which we do by comparing it with 0, in
                                # signed terms that would make it negative)
                                Cmp(size=64, lhs=Imm(root=0), rhs=src_v),
                                JmpCC(cond="l", label=label_1.root),
                                CvtSI2SD(src=src_v, dest=dest_v, src_size=size),
                                Jmp(root=label_end.root),
                                label_1,
                                # else...we do this thing called `rounding-to-odd`.
                                # It's a super weird algorithm. The book spends a long time
                                # going over it. I'm 1000% sure I don't get it.
                                # TLDR: Half the value, ensuring we round to an odd number
                                # so that the rounding doesn't have problems due to
                                # floating-point shenanigans.
                                Mov(size=64, src=src_v, dest=scratch_1),
                                Mov(size=64, src=scratch_1, dest=scratch_2),
                                Unary(op="RIGHT_SHIFT", size=64, operand=scratch_2),
                                Binary(
                                    op="PLUS",
                                    src=Imm(root=1),
                                    dest=scratch_1,
                                    size=64,
                                    is_signed=False,
                                ),
                                Binary(
                                    op="PIPE",
                                    src=scratch_1,
                                    dest=scratch_2,
                                    size=64,
                                    is_signed=False,
                                ),
                                # We convert this halfed value to a double
                                CvtSI2SD(src=scratch_2, dest=dest_v, src_size=size),
                                # And then we add the double to itself.
                                # There'll be _some_ rounding, but less than if we just
                                # halved the whole thing.
                                Binary(
                                    op="PLUS",
                                    src=dest_v,
                                    dest=dest_v,
                                    size=128,
                                    is_signed=False,
                                ),
                                label_end,
                            )
                        )

                case tacky.DoubleToInt(src=src, dest=dest):
                    size = BST.get_size(dest)
                    instructions.append(
                        CvtTSD2SI(
                            src=get_val(src),
                            dest=get_val(dest),
                            dest_size=size,  # pyright: ignore[reportArgumentType]
                        )
                    )

                case tacky.DoubleToUInt(src=src, dest=dest):
                    size = BST.get_size(dest)
                    if size == 32:
                        # We do a `mov_zero_extend` so that later on in part III we don't optimize
                        # it away!
                        instructions.extend(
                            (
                                CvtTSD2SI(
                                    src=get_val(src),
                                    dest=GeneralReg(root="R11", size=32),
                                    # It _will_ be less than 128
                                    # because we don't do 128 ints
                                    dest_size=32,
                                ),
                                Mov(
                                    size=32,
                                    src=GeneralReg(root="R11", size=32),
                                    dest=get_val(dest),
                                ),
                            )
                        )
                    else:
                        src_v = get_val(src)
                        dest_v = get_val(dest)
                        upper_val = float(dt.x64.max[64] + 1)
                        upper_bound = Static_Variable.from_local(
                            parser.Constant(
                                root=upper_val,
                                ctype=parser.CType(root="double"),
                            ),
                            static_variables,
                            alignment=8,
                        )
                        upper_data = Data(root=upper_bound.name)

                        label_1 = Label(
                            root=semantic_analysis.get_new_name("out_of_range"),
                            local=True,
                        )
                        label_end = Label(
                            root=semantic_analysis.get_new_name("end"), local=True
                        )

                        scratch_xmm = XMM(root=11)
                        scratch = GeneralReg.get_scratch(which="D", size=64)

                        instructions.extend(
                            (
                                Cmp(size=128, lhs=upper_data, rhs=src_v),
                                JmpCC(cond="ae", label=label_1.root),
                                # If it's bellow or equal to our upper bound
                                # We can do a normal conversion
                                # TODO(Joaquim): Unsure about this src_size stuff
                                CvtTSD2SI(src=src_v, dest=dest_v, dest_size=64),
                                Jmp(root=label_end.root),
                                label_1,
                                Mov(size=128, src=src_v, dest=scratch_xmm),
                                # We subtract our upper bound from it, do the conversion
                                # and then add it back :)
                                Binary(
                                    op="MINUS",
                                    src=upper_data,
                                    dest=scratch_xmm,
                                    is_signed=False,
                                    size=128,
                                ),
                                CvtTSD2SI(src=scratch_xmm, dest=dest_v, dest_size=64),
                                Mov(
                                    size=64, src=Imm(root=int(upper_val)), dest=scratch
                                ),
                                Binary(
                                    op="PLUS",
                                    src=scratch,
                                    dest=dest_v,
                                    is_signed=False,
                                    size=64,
                                ),
                                label_end,
                            )
                        )

                case tacky.ZeroExtend(src=src, dest=dest):
                    instructions.append(
                        Mov_Zero_Extend(src=get_val(src), dest=get_val(dest)),
                    )
                case tacky.Truncate(src=src, dest=dest):
                    instructions.append(
                        Mov(
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
                    reg = (
                        GeneralReg(root="A", size=size) if size != 128 else XMM(root=0)
                    )
                    instructions.extend(
                        [
                            Mov(
                                size=size,
                                src=src,
                                dest=reg,
                            ),
                            Return(),
                        ]
                    )

                case tacky.Unary():
                    instructions.extend(
                        Unary.from_tacky(inst, get_val, static_variables)
                    )

                case tacky.BinaryOp(src1=src1):
                    instructions.extend(
                        Binary.from_tacky(inst, get_val, is_signed=BST.is_signed(src1))
                    )

                case tacky.Copy(src=src, dest=dest):
                    instructions.append(
                        Mov(
                            size=BST.get_size(src), src=get_val(src), dest=get_val(dest)
                        )
                    )

                case (
                    tacky.JumpIfZero(target=target, condition=condition)
                    | tacky.JumpIfNotZero(target=target, condition=condition)
                ):
                    label = target if isinstance(target, str) else target.identifier
                    size = BST.get_size(condition)
                    jump = JmpCC(
                        cond="e" if isinstance(inst, tacky.JumpIfZero) else "ne",
                        label=label,
                    )
                    if size != 128:
                        instructions.extend(
                            (
                                Cmp(size=size, lhs=Imm(root=0), rhs=get_val(condition)),
                                jump,
                            )
                        )
                    else:
                        # To use the cmp with floats stuff must go into a register
                        # xoring a thing by itself always yields 0
                        instructions.extend(
                            (
                                Binary(
                                    op="CARRET",
                                    size=128,
                                    is_signed=True,
                                    src=XMM(root=0),
                                    dest=XMM(root=0),
                                ),
                                Cmp(size=size, lhs=get_val(condition), rhs=XMM(root=0)),
                                jump,
                            )
                        )

                case tacky.Jump(target=target):
                    label = target if isinstance(target, str) else target.identifier
                    instructions.append(Jmp(root=label))

                case tacky.Label(identifier=identifier):
                    instructions.append(Label(root=identifier, local=False))

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
                ass_i = i.to_assembly()
                if isinstance(ass_i, str):
                    temp.extend(ass_i.split("\n"))
                else:
                    temp.extend(ass_i)

                res.append(f"\t{'\n\t'.join(temp)}")
        else:
            flat: list[list[str]] = [
                i.split("\n")
                for i in pf.flatten(*[i.to_assembly() for i in self.instructions])
            ]
            res.extend(f"\t{'\n\t'.join(i)}" for i in flat)

        return res


class Comment(BaseModel):
    root: object

    def to_assembly(self) -> str:
        return f"# TACKY {self.root!s}"


class Mov(_Sized):
    src: Operand
    dest: Operand

    def to_assembly(self) -> str:
        src, dest, size = self.src, self.dest, self.size

        def default():
            return (
                f"mov{self.assembly_type()} {src.to_assembly()}, {dest.to_assembly()}"
            )

        def with_scratch():
            scratch = GeneralReg.get_scratch(size=self.size)
            return "\n".join(
                [
                    Mov(size=size, src=src, dest=scratch).to_assembly(),
                    Mov(size=size, src=scratch, dest=dest).to_assembly(),
                ]
            )

        match src, dest:
            case Stack() | Data(), Stack() | Data():
                # It's illegal to mov from one mem-address into another
                # So we need to move to a strach register
                return with_scratch()

            case Imm(), GeneralReg():
                return default()

            case Imm(), Imm():
                raise ValueError("Compiler error")

            case Imm(), _:
                if t.TYPE_CHECKING:
                    assert self.size != 128

                src = src.truncate(self.size)
                if abs(src.root) < dt.x64.max[32]:
                    return default()

                # Large boys must go into a register first _before_ they go into whatever
                # destination they were meant
                return with_scratch()

            case _:
                # just one mov is fine
                return default()


class Mov_Zero_Extend(_SrcDest):
    def to_assembly(self) -> str:
        # We zero extend by moving some 32 bit thing into a register
        # Doing so will zero out the 4 high bytes.

        if isinstance(self.dest, GeneralReg):
            # Excellent, we can do it in just one mov
            return Mov(src=self.src, dest=self.dest, size=32).to_assembly()

        scratch = GeneralReg(root="R11", size=32)
        return "\n".join(
            (
                Mov(src=self.src, dest=scratch, size=32).to_assembly(),
                Mov(
                    src=GeneralReg(root="R11", size=64), dest=self.dest, size=64
                ).to_assembly(),
            )
        )


class CvtSI2SD(_SrcDest):
    """
    Name mnemonic:
    CVT(Convert) Signed Integer (SI) 2 Scalar-Double (SD)

    The cvtsi2sd instruction has two constraints: the source can't be a
    constant, and the destination must be a register.

    """

    src_size: dt.x64.Bit_Size

    def to_assembly(self):
        suffix = dt.x64.from_bit_size[self.src_size]

        def inner(this: CvtSI2SD) -> abc.Generator[str]:
            if isinstance(this.src, Imm):
                scratch = XMM(root=15)
                yield Mov(size=128, src=this.src, dest=scratch).to_assembly()
                yield from inner(this.model_copy(update={"src": scratch}))
                return
            if not isinstance(this.dest, XMM):
                scratch = XMM(root=14)
                yield from inner(this.model_copy(update={"dest": scratch}))
                yield Mov(size=128, src=scratch, dest=this.dest).to_assembly()
                return
            yield f"cvtsi2sd{suffix} {this.src.to_assembly()}, {this.dest.to_assembly()}"

        return list(pf.flatten(*inner(self)))


class CvtTSD2SI(_SrcDest):
    """
    Name mnemonic:
    CVT(Convert) with Truncation (T) Scalar Double (SI) 2 Signed-Integer (SD)
    """

    dest_size: dt.x64.Bit_Size

    def to_assembly(self) -> abc.Generator[str]:
        # We zero extend by moving some 32 bit thing into a register
        # Doing so will zero out the 4 high bytes.

        suffix = dt.x64.from_bit_size[self.dest_size]
        if not isinstance(self.dest, GeneralReg):
            scratch = GeneralReg.get_scratch(size=self.dest_size)
            yield from self.model_copy(update={"dest": scratch}).to_assembly()
            yield Mov(size=self.dest_size, src=scratch, dest=self.dest).to_assembly()
            return
        yield f"cvttsd2si{suffix} {self.src.to_assembly()}, {self.dest.to_assembly()}"


class Movsx(BaseModel):
    src: Operand
    dest: Operand

    @staticmethod
    def new(src: Operand, dest: Operand) -> list[Movsx | Mov]:
        dest_is_mem = isinstance(dest, (Stack, Data))
        source_is_imm = isinstance(src, Imm)
        if dest_is_mem or source_is_imm:
            # Just like a normal mov, we have to do some tweaking
            return [
                Mov(size=32, src=src, dest=GeneralReg(root="R10", size=32)),
                Movsx(
                    src=GeneralReg(root="R10", size=32),
                    dest=GeneralReg(root="R11", size=64),
                ),
                Mov(size=64, src=GeneralReg(root="R11", size=64), dest=dest),
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


class Unary(_Sized):
    op: tacky.Simple_Unary | t.Literal["RIGHT_SHIFT"]
    operand: Operand

    def to_assembly(self) -> str:
        match self.op:
            case "COMPLEMENT":
                return f"not{self.assembly_type()} {self.operand.to_assembly()}"
            case "MINUS":
                # IF IT'S A DOUBLE WE NEED TO USE A XOR
                return f"neg{self.assembly_type()} {self.operand.to_assembly()}"
            case "RIGHT_SHIFT":
                return f"shr{self.assembly_type()} {self.operand.to_assembly()}"

    @staticmethod
    def from_tacky(
        arg: tacky.Unary, get_val: Get_Val, static_variables: list[Static_Variable]
    ) -> tuple[Instruction, ...]:
        match arg:
            case tacky.Unary(
                operation="NOT",
                source=source,
                destination=destination,
            ) if BST.is_double(source):
                # Shiiiiiiit
                # A !0.0 is actually super tricky (for some reason???)
                # We have to use `xorpd` remembering that to use xorpd
                # the alignment has to be 16
                scratch = XMM(root=15)

                dest_size = BST.get_size(destination)
                dest_v = get_val(destination)

                if dest_size == 128:
                    # GODDAMMIT (This _should_) not be possible!
                    positive_zero = Static_Variable.from_local(
                        parser.Constant(root=0.0, ctype=parser.CType(root="double")),
                        static_variables,
                        alignment=16,
                    )
                    zero = Data(root=positive_zero.name)
                else:
                    zero = Imm(root=0)

                return (
                    Binary(
                        op="CARRET",
                        size=128,
                        src=scratch,
                        dest=scratch,
                        is_signed=True,
                    ),
                    Cmp(size=128, lhs=get_val(source), rhs=scratch),
                    Mov(size=dest_size, src=zero, dest=dest_v),
                    SetCC(cond="e", operand=dest_v),  # pyright: ignore[reportArgumentType]
                )

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
                operation="MINUS",
                source=source,
                destination=destination,
            ) if BST.is_double(source):
                # Shiiiiiiit
                # We have to use `xorpd` remembering that to use xorpd
                # the alignment has to be 16
                negative_zero = Static_Variable.from_local(
                    parser.Constant(root=-0.0, ctype=parser.CType(root="double")),
                    static_variables,
                    alignment=16,
                )
                const = Data(root=negative_zero.name)
                src = get_val(source)
                dest = get_val(destination)
                return (
                    Mov(size=128, src=src, dest=dest),
                    Binary(
                        op="CARRET",
                        size=128,
                        src=const,
                        dest=dest,
                        is_signed=True,
                    ),
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
                    Mov(
                        size=size,
                        src=src,
                        dest=dest,
                    ),
                    Unary(
                        size=size,
                        op=operation,  # pyright: ignore[reportArgumentType]
                        operand=dest,
                    ),
                )


class Binary(_Sized):
    op: parser.Simple_Binary | t.Literal["DivDouble"]
    src: Operand
    dest: Operand
    is_signed: bool

    _must_be_in_reg: t.ClassVar[set[parser.Simple_Binary | t.Literal["DivDouble"]]] = {
        "MINUS",
        "PLUS",
        "DivDouble",
        "CARRET",
        "ASTERISK",
    }

    def to_assembly(self) -> str:
        def match_op(op: parser.Simple_Binary | t.Literal["DivDouble"]):
            match op:
                case "MINUS":
                    return "sub"
                case "PLUS":
                    return "add"
                case "ASTERISK":
                    return "imul" if self.size != 128 else "mul"
                # BUG HERE - apparently they change
                # according to if they are signed, size and I dunno what
                case "LEFT_SHIFT":
                    return "sal" if self.is_signed else "shl"
                case "RIGHT_SHIFT":
                    return "sar" if self.is_signed else "shr"
                case "AMPERSAND":
                    return "and"
                case "PIPE":
                    return "or"
                case "CARRET":
                    # NOTE: THERE'S NO XORSD - INSTEAD WE NEED TO DO xorpd
                    return "xor"
                case "DivDouble":
                    return "div"

        ass_op = f"{match_op(self.op)}{self.assembly_type()}"
        if ass_op == "xorsd":
            # HACK
            ass_op = "xorpd"

        match (self.op, self.src, self.dest):
            case "PLUS" | "MINUS" | "ASTERISK" | "LEFT_SHIFT" | "RIGHT_SHIFT", _, Imm():
                raise ValueError(
                    "Bad assembly! Destination can't be a constant! It holds the result"
                )

            case "ASTERISK", _, Stack() | Data():
                scratch = GeneralReg.get_scratch("R11", size=self.size)
                pre = Mov(
                    src=self.dest,
                    dest=scratch,
                    size=self.size,
                )
                after = Mov(
                    src=scratch,
                    dest=self.dest,
                    size=self.size,
                )
                return (
                    f"{pre.to_assembly()}\n"
                    f"{self.model_copy(update={'dest': scratch}).to_assembly()}\n"
                    f"{after.to_assembly()}"
                )

            case "LEFT_SHIFT" | "RIGHT_SHIFT", GeneralReg() | Stack() | Data(), _:
                # Left and right shift have a special rule
                # From the manual: https://www.felixcloutier.com/x86/sal:sar:shl:shr
                # > The destination operand can be a register or a memory
                # > location. The count operand can be an immediate value or
                # > the CL register
                # The source must be either a constant, or on the special %CL register
                scratch = GeneralReg.get_scratch("C", 8)
                pre = Mov(size=8, src=self.src, dest=scratch)
                return (
                    f"{pre.to_assembly()}\n"
                    f"{self.model_copy(update={'src': scratch}).to_assembly()}\n"
                )
            case _, Stack() | Data(), Stack() | Data():
                scratch = GeneralReg.get_scratch(size=self.size)
                pre = Mov(size=self.size, src=self.src, dest=scratch)
                return (
                    f"{pre.to_assembly()}\n"
                    f"{self.model_copy(update={'src': scratch}).to_assembly()}\n"
                )

            case _, Imm(), __:
                src = self.src.truncate(self.size)  # pyright: ignore[reportArgumentType]
                if abs(src.root) < dt.x64.max[32]:
                    return f"{ass_op} {src.to_assembly()}, {self.dest.to_assembly()}"
                # Danggit. Just like `mov` they must first go into a register
                scratch = GeneralReg.get_scratch(size=self.size)
                pre = Mov(size=self.size, src=src, dest=scratch)
                return (
                    f"{pre.to_assembly()}\n"
                    f"{self.model_copy(update={'src': scratch}).to_assembly()}\n"
                )

            case _, _, Stack() | Data() if (
                self.size == 128 and self.op in self._must_be_in_reg
            ):
                scratch = XMM(root=15)
                pre = Mov(size=self.size, src=self.dest, dest=scratch)
                post = Mov(size=self.size, src=scratch, dest=self.dest)
                return (
                    f"{pre.to_assembly()}\n"
                    f"{self.model_copy(update={'dest': scratch}).to_assembly()}\n"
                    f"{post.to_assembly()}\n"
                )

            case _:
                return f"{ass_op} {self.src.to_assembly()}, {self.dest.to_assembly()}"

    @staticmethod
    def from_tacky(
        inst: tacky.BinaryOp,
        get_val: Get_Val,
        is_signed: bool,  # noqa: FBT001
    ) -> tuple[Instruction, ...]:
        src1 = get_val(inst.src1)
        src2 = get_val(inst.src2)
        dest = get_val(inst.dest)

        is_double = any(BST.is_double(v) for v in (inst.src1, inst.src2))

        size = BST.get_size(inst.src1)
        match inst.operation:
            case "FORWARD_SLASH" | "PERCENT":
                # Division/remainder - are a bit of an ass
                # TODO(Joaquim): FIX THIS - FOR FLOATS WE DON'T NEED TO DO THIS STUFF

                if is_double:
                    # Float division is special.
                    return (
                        Mov(size=128, src=src1, dest=dest),
                        Binary(
                            op="DivDouble",
                            size=128,
                            src=src2,
                            dest=dest,
                            is_signed=is_signed,
                        ),
                    )

                if t.TYPE_CHECKING:
                    assert size != 128

                if is_signed:
                    # `idiv` slaps the result in `A` and the remainder in `D`
                    return (
                        Mov(size=size, src=src1, dest=GeneralReg(root="A", size=size)),
                        Cdq(size=size),
                        Idiv(size=size, root=src2),
                        Mov(
                            size=size,
                            src=GeneralReg(
                                root="A" if inst.operation == "FORWARD_SLASH" else "D",
                                size=size,
                            ),
                            dest=dest,
                        ),
                    )

                return (
                    Mov(size=size, src=src1, dest=GeneralReg(root="A", size=size)),
                    Mov(
                        size=size, src=Imm(root=0), dest=GeneralReg(root="D", size=size)
                    ),
                    Div(size=size, root=src2),
                    Mov(
                        size=size,
                        src=GeneralReg(
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
                        cond=map_relational_to_cond_code(
                            inst.operation, is_signed=is_signed, is_double=is_double
                        ),
                        operand=dest,  # pyright: ignore[reportArgumentType]
                    ),
                )

            case _arrithmetic:
                return (
                    Mov(size=size, src=src1, dest=dest),
                    Binary(
                        size=size,
                        op=inst.operation,  # pyright: ignore[reportArgumentType]
                        src=src2,
                        dest=dest,
                        is_signed=is_signed,
                    ),
                )
        raise ValueError("unreachable")  # pyright: ignore[reportUnreachable]


class Cmp(_Sized):
    lhs: Operand
    rhs: Operand

    def to_assembly(self) -> list[str]:
        # Just to be annoying, floats have a different prefix
        prefix = "cmp" if self.size != 128 else "comi"

        def inner(this: Cmp) -> abc.Generator[str]:
            match this.lhs, this.rhs:
                case (Stack() | Data(), Stack() | Data()):
                    scratch = GeneralReg.get_scratch(size=this.size)

                    yield Mov(src=this.lhs, dest=scratch, size=this.size).to_assembly()
                    yield from inner(this.model_copy(update={"lhs": scratch}))

                case _, Stack() | Data() if this.size == 128:
                    # comisd's destinaton _must_ be a register
                    scratch = XMM(root=15)
                    yield Mov(size=128, src=this.rhs, dest=scratch).to_assembly()
                    yield from inner(this.model_copy(update={"rhs": scratch}))

                case _, Imm():
                    # The destination can never be an Immediate
                    # (This seems weird, shouldn't I just switch them?)
                    scratch = GeneralReg.get_scratch(size=this.size)
                    yield Mov(src=this.rhs, dest=scratch, size=this.size).to_assembly()
                    yield from inner(this.model_copy(update={"rhs": scratch}))

                case Imm(), _:
                    src = this.lhs.truncate(this.size)  # pyright: ignore[reportArgumentType]

                    if abs(src.root) < dt.x64.max[32]:
                        yield f"{prefix}{this.assembly_type()} {src.to_assembly()}, {this.rhs.to_assembly()}"
                        return

                    # shit! We have to first mov them
                    scratch = GeneralReg.get_scratch(size=this.size)
                    yield Mov(size=this.size, src=src, dest=scratch).to_assembly()
                    yield from inner(this.model_copy(update={"lhs": scratch}))

                case _:
                    yield f"{prefix}{this.assembly_type()} {this.lhs.to_assembly()}, {this.rhs.to_assembly()}"

        return list(pf.flatten(*inner(self)))


class Jmp(BaseModel):
    root: Identifier_For_Assembly

    def to_assembly(self) -> str:
        return f"jmp {self.root}"


class JmpCC(BaseModel):
    label: Identifier_For_Assembly
    cond: Cond_Code

    def to_assembly(self) -> str:
        return f"j{self.cond} {self.label}"


class SetCC(BaseModel):
    operand: Stack | Reg
    cond: Cond_Code

    def to_assembly(self) -> str:
        return f"set{self.cond} {_get_8_bit(self.operand).to_assembly()}"


class Label(BaseModel):
    root: tacky.Valid_Identifier
    """
    We keep the old `Valid_Identifier` to transform any weird stuff the get_new_name passes us
    """
    local: bool

    @model_validator(mode="after")
    def tweak_name(self):
        if self.local and not self.root.startswith(".L_"):
            self.root = f".L_{self.root}"
        return self

    def to_assembly(self) -> str:
        return f"{self.root}:"


# TODO(Joaquim): THESE NERDS ARE DIFFERENT FOR FLOATING POINTS
# THERE'S NO NEED TO DO ALL OF THIS MOVING CRAP
# WE NEED TO EDIT WERE THEY ARE CREATED TOO


class Idiv(_Sized):
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
                scratch = GeneralReg.get_scratch(size=self.size)
                return (
                    f"{Mov(size=self.size, src=self.root, dest=scratch).to_assembly()}\n"
                    f"idiv{self.assembly_type()} {scratch.to_assembly()}"
                )
            case _:
                return f"idiv{self.assembly_type()} {self.root.to_assembly()}"


class Div(_Sized):
    root: Operand

    def to_assembly(self) -> str:
        match self.root:
            case Imm():
                # You can't divide a constant value
                # It must first go into the scratch register
                scratch = GeneralReg.get_scratch(size=self.size)
                return (
                    f"{Mov(size=self.size, src=self.root, dest=scratch).to_assembly()}\n"
                    f"div{self.assembly_type()} {scratch.to_assembly()}"
                )
            case _:
                return f"div{self.assembly_type()} {self.root.to_assembly()}"


class Cdq(_Sized):
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
        size=64,
        op="MINUS",
        src=Imm(root=abs(bytes)),
        dest=GeneralReg(root="SP", size=64),
        is_signed=False,
    )


def de_allocate_stack(bytes: int):
    return Binary(
        size=64,
        op="PLUS",
        src=Imm(root=abs(bytes)),
        dest=GeneralReg(root="SP", size=64),
        is_signed=False,
    )


class Push(BaseModel):
    operand: Operand

    def to_assembly(self) -> str:
        match self.operand:
            case Imm(root=root) if root >= dt.x64.max[32]:
                scratch = GeneralReg.get_scratch(size=64)
                pre = Mov(size=64, src=self.operand, dest=scratch)
                return f"{pre.to_assembly()}\npushq {scratch.to_assembly()}"
            case _:
                return f"pushq {self.operand.to_assembly()}"


class Call(BaseModel):
    name: Identifier_For_Assembly

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
                case GeneralReg(root=root):
                    # Ensure we're pushing
                    # only 64 bits
                    instructions.append(Push(operand=GeneralReg(root=root, size=64)))
                case Imm():
                    instructions.append(Push(operand=val))
                case _ if size == 64:
                    # We can just push it! No problemo
                    instructions.append(Push(operand=val))
                case _:
                    # If it's in memory and NOT 64 bits then we must first move our 32 value
                    # into the A register
                    # Then we can push _that_ register over to the stack no problem
                    accumulator_small = GeneralReg(root="A", size=32)
                    accumulator = GeneralReg(root="A", size=64)

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
        reg = (
            GeneralReg(root="A", size=return_size)
            if return_size != 128
            else XMM(root=0)
        )
        instructions.append(
            Mov(
                size=return_size,
                src=reg,
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
        return f"${hex(abs(self.root))}"

    def truncate(self, size: dt.x64.Bit_Size = 32):
        return Imm(root=self.root & dt.x64.umax[size])


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


type Reg = GeneralReg | XMM


class GeneralReg(BaseModel):
    root: dt.x64.Register
    size: dt.x64.Bit_Size

    @staticmethod
    def get_scratch(
        which: t.Literal["R10", "R11", "C", "D"] | None = None, size: int = 32 | 128
    ):
        # pyright will cry if we pass it the wrong guy
        if size == 128:
            return XMM(root=11)
        if which is None:
            which = "R11"
        return GeneralReg(root=which, size=size)  # pyright: ignore[reportArgumentType]

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


class XMM(BaseModel):
    root: t.Literal[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

    def to_assembly(self):
        return f"%xmm{self.root}"


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
    root: Identifier_For_Assembly

    def to_assembly(self):
        return f"{self.root}(%rip)"


class Stack(BaseModel):
    root: int

    def to_assembly(self) -> str:
        return f"{self.root}(%rbp)"


class Ass(RootModel[str]):
    pass


def static_var_to_assembly(var: Static_Variable):
    # TODO(Joaquim): Don't forget the `.L_` when creating a float immediate
    global_directive = f".globl {var.name}" if var.is_global else ""

    match var.init.val, var.type.root:
        case _, parser.CType.FuncType():
            raise TypeError("What is a function doing here?")
        case _, "double":
            section, actual_data = (
                ".section .rodata" if var.is_constant else ".data",
                f".double {var.init.val}",
            )
        case float(), _:
            raise ValueError("Compiler skill issue")
        case 0, "int" | "uint":
            section, actual_data = (".bss", ".zero 4")
        case 0, "long" | "ulong":
            section, actual_data = (".bss", ".zero 8")
        case int(), "int" | "uint":
            section, actual_data = (".data", f".long {var.init.val}")
        case int(), "long" | "ulong":
            section, actual_data = (".data", f".quad {var.init.val}")

    text = f"""\
	{global_directive} 
	{section}
	.align {var.alignment}
{var.name}:
	{actual_data}"""

    return dedent(text)


def _get_8_bit(operand: Stack | GeneralReg | XMM):
    match operand:
        case Stack() | XMM():
            return operand
        case GeneralReg(root=root):
            return GeneralReg(root=root, size=8)


# TODO(Joaquim): THIS IS WRONG!!!!!!!!!!!!
# THE INDEX IS NOT ENOUGH ANYMORE
def _get_system_v_call_convention(index: int, size: dt.x64.Bit_Size | t.Literal[128]):
    if size != 128:
        reg = dt.x64.from_arg_number.get(index)
        if reg is None:
            # They're already on the stack!
            # Thanks System V ABI
            # Stack[0] will always be the BASE
            # RBP + 16 bytes is always the 7th argument passed.
            # See `chapter13/README.md:196`
            # Note: when we add different CTypes I'll have to tweak this
            return Stack(root=16 + 8 * (index - 6))
        return GeneralReg(root=reg, size=size)

    # shiiiiit
    if index < 8:
        return XMM(root=index)  # pyright: ignore[reportArgumentType]

    return Stack(root=16 + 16 * (index - 6))
