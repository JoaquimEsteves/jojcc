"""
underscore denotes new shit

```
program = Program(function_definition)
function_definition = Function(identifier, instruction* body)
instruction = Return(val)
            | Unary(unary_operator, val src, val dst)
            | Binary(binary_operator, val src1, val src2, val dst)
            | _Copy(val src, val dst)_
            | _Jump(identifier target)_
            | _JumpIfZero(val condition, identifier target)_
            | _JumpIfNotZero(val condition, identifier target)_
            | _Label(identifier)_
val = Constant(int) | Var(identifier)
unary_operator = Complement | Negate | _Not_
binary_operator = Add | Subtract | Multiply | Divide | Remainder | _Equal_ | _NotEqual_
                | _LessThan_ | _LessOrEqual_ | _GreaterThan_ | _GreaterOrEqual_
```

Relational operatios in tacky basically go like this (except for && and ||):

```
<instructions for e1>
v1 = <result of e1>
<instructions for e2>
v2 = <result of e2>
Binary(LessThan, v1, v2, result)
```

The `AND` and the `OR` however require something like the following tacky:

```
v1 = <result of e1>
JumpIfZero(v1, 'false_label)
v2 = <result of e2>
JumpIfZero(v2, 'false_label)
result = 1
Jump(end)
Label('false_label)
result = 0
Label(end)
```
"""

import typing as t
from textwrap import dedent

from pydantic import BaseModel

from chapter6 import parser, semantic_analysis
from shared import data_types as dt
from shared import pure_functions as pf


class Program(BaseModel):
    function_def: "Function"

    @staticmethod
    def from_ast(prog: parser.Program):
        instructions: list[Instruction] = []
        return Program(function_def=Function.from_ast(prog.function, instructions))


class Function(BaseModel):
    name: str
    instructions: "list[Instruction]"
    return_type: parser.CType

    @staticmethod
    def from_ast(ast: parser.Function, instructions: list[Instruction]):
        for line in ast.body:
            if isinstance(line, parser.Statement) and line.root == "nope":
                continue
            _ = emit_tacky(line, instructions)
        return Function(
            name=ast.name.root,
            return_type=ast.return_type,
            instructions=instructions,
        )

    @t.override
    def __repr__(self):
        start = pf.indent(
            dedent(
                f"""
                    (function
                      ('name {self.name})
                      ('return_type {self.return_type.root})
                      ('body 
                """
            )
        )
        with pf.set_context(dt.INDENT_LEVEL, dt.INDENT_LEVEL.get() + 2):
            body = pf.indent("\n".join(repr(b) for b in self.instructions))

        return f"{start}{body})"


type Instruction = (
    Return | Unary | BinaryOp | Copy | Jump | JumpIfZero | JumpIfNotZero | Label
)
type Value = parser.Constant | Var


class Return(BaseModel):
    root: Value | None

    @t.override
    def __repr__(self):
        return f"(return {repr(self.root)})"


class Var(BaseModel):
    name: str

    @t.override
    def __repr__(self):
        return f"`{self.name}`"


type Simple_Unary = t.Literal["COMPLEMENT", "MINUS"]
type Unary_Op = Simple_Unary | t.Literal["NOT"]


class Unary(BaseModel):
    operation: Unary_Op
    source: Value
    destination: Value

    @t.override
    def __repr__(self):
        return f"({self.operation} {repr(self.source)} {repr(self.destination)})"


class BinaryOp(BaseModel):
    operation: parser.Binary_Operation
    src1: Value
    src2: Value
    dest: Value

    @t.override
    def __repr__(self):
        return f"({self.operation} {repr(self.src1)} {repr(self.src2)})\n({self.operation} {repr(self.src2)} {repr(self.dest)})"


class Copy(BaseModel):
    src: Value
    dest: Value

    @t.override
    def __repr__(self):
        return f"(copy {repr(self.src)} {repr(self.dest)})"


class Jump(BaseModel):
    """
    Interesting note on how `jump` works in assembly

    ```asm
        addl $1, %eax
        jmp foo
        movl $0, %eax
    foo:
        ret
    ```

    The assembler and linker will replace `foo` with `jump 5`.
    This is because the instruction `movl $0, %eax` is 5 bytes long.
    So we increment a special `RIP` address by 5, hence skipping the movl
    """

    target: dt.Identifier


class JumpIfZero(Jump):
    condition: Value


class JumpIfNotZero(Jump):
    condition: Value


class Label(BaseModel):
    identifier: dt.Identifier


def make_temp(label: str = "_TMP_"):
    semantic_analysis.Global_Counter += 1
    return f"{label}-{semantic_analysis.Global_Counter}"


def make_label(label: str):
    semantic_analysis.Global_Counter += 1
    return f"{label}.{semantic_analysis.Global_Counter}"


def emit_tacky(
    block: parser.Expression | parser.Block_Item,
    instructions: list[Instruction],
) -> Value:
    """
    Mutates instructions (if they exist)
    """

    match block:
        case parser.Expression():
            return emit_exp(block, instructions)
        case parser.Statement():
            match block.root:
                case parser.ReturnStatement(exp=expression):
                    final = emit_tacky(expression, instructions)
                    instructions.append(Return(root=final))
                    return final
                case parser.Expression():
                    return emit_tacky(block.root, instructions)
                case "nope":
                    raise ValueError("This should not be here!")
        case parser.Declaration(name=name, init=init):
            var = Var(name=name.root)
            if init:
                result = emit_tacky(init, instructions)
                assert result
                instructions.append(Copy(src=result, dest=var))
            return var


def emit_exp(
    exp: parser.Expression,
    instructions: list[Instruction],
) -> Value:
    match exp.type:
        case parser.Factor(type=type):
            match type:
                case parser.Identifier(root=name):
                    return Var(name=name)
                case parser.Constant():
                    return type
                case parser.Unary(type=operation, exp=factor, pre=pre):
                    source = emit_tacky(parser.Expression(type=factor), instructions)
                    destination: Value
                    if operation not in ("++", "--"):
                        destination = Var(name=make_temp())
                        instructions.append(
                            Unary(
                                operation=operation,
                                source=source,
                                destination=destination,
                            )
                        )
                        return destination

                    current: t.Any = factor
                    while hasattr(current, "type"):  # pyright: ignore[reportAny]
                        current = current.type  # pyright: ignore[reportAny]
                    assert isinstance(current, parser.Identifier), (
                        f"{current} is not assignable!"
                    )

                    lhs = parser.Expression(type=factor)
                    rhs = parser.Expression(
                        type=parser.Factor(type=parser.Constant(root=1))
                    )
                    intermediate_exp = parser.Expression(
                        type=parser.BinaryOp(
                            type="PLUS" if operation == "++" else "MINUS",
                            lhs=lhs,
                            rhs=rhs,
                        )
                    )

                    if pre:
                        destination = emit_exp(
                            parser.Expression(
                                type=parser.NormalAssigment(
                                    lhs=current, rhs=intermediate_exp
                                )
                            ),
                            instructions,
                        )
                    else:
                        destination = Var(name=make_temp())
                        instructions.append(Copy(src=source, dest=destination))

                        _ = emit_exp(
                            parser.Expression(
                                type=parser.NormalAssigment(
                                    lhs=current, rhs=intermediate_exp
                                )
                            ),
                            instructions,
                        )

                    return destination
                case parser.Expression():
                    return emit_tacky(type, instructions)
        case parser.FancyAssignment():
            raise ValueError("Should have been gone by this stage!")
        case parser.NormalAssigment(lhs=parser.Identifier(root=name), rhs=rhs):
            var = Var(name=name)
            res = emit_tacky(rhs, instructions)

            instructions.append(Copy(src=res, dest=var))
            return var
        case parser.BinaryOp(type=bin_op, lhs=lhs, rhs=rhs):
            match bin_op:
                case "AND":
                    end = make_label("and_end")
                    dst = Var(name=make_temp("result_and"))
                    tmp = Var(name=make_temp("tmp"))

                    # DON'T use `extend` for the whole thing!
                    # The eval-order will be wrong, the instructions will be appendded out of order!
                    # As the inner `emit_tacky` will "win"
                    instructions.append(Copy(src=parser.Constant(root=0), dest=dst))
                    v1 = emit_tacky(lhs, instructions)
                    instructions.append(Copy(src=v1, dest=tmp))
                    instructions.append(JumpIfZero(condition=tmp, target=end))
                    instructions.append(
                        Copy(src=emit_tacky(rhs, instructions), dest=tmp)
                    )
                    instructions.extend(
                        (
                            JumpIfZero(condition=tmp, target=end),
                            Copy(src=parser.Constant(root=1), dest=dst),
                            Label(identifier=end),
                        ),
                    )
                    return dst
                case "OR":
                    end = make_label("or_end")
                    dst = Var(name=make_temp("result_or"))
                    tmp = Var(name=make_temp("tmp"))

                    instructions.append(Copy(src=parser.Constant(root=1), dest=dst))
                    # OPTIMIZATION - only move `copy` if the var is not a constant
                    instructions.append(
                        Copy(src=emit_tacky(lhs, instructions), dest=tmp)
                    )

                    # If lhs is not zero then exit
                    # We already set the return to 1
                    instructions.append(JumpIfNotZero(condition=tmp, target=end))
                    instructions.append(
                        Copy(src=emit_tacky(rhs, instructions), dest=tmp)
                    )

                    instructions.extend(
                        (
                            JumpIfNotZero(condition=tmp, target=end),
                            Copy(src=parser.Constant(root=0), dest=dst),
                            Label(identifier=end),
                        )
                    )

                    return dst
                case _:
                    v1 = emit_tacky(lhs, instructions)
                    v2 = emit_tacky(rhs, instructions)
                    dst = Var(name=make_temp("_tmp_bin_op_result"))
                    instructions.append(
                        BinaryOp(operation=bin_op, src1=v1, src2=v2, dest=dst)
                    )
                    return dst
