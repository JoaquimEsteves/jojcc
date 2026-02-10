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

from chapter4 import parser

from pydantic import BaseModel
import shared.data_types as dt


class Program(BaseModel):
    function_def: "Function"

    @staticmethod
    def from_ast(prog: parser.Program):
        return Program(function_def=Function.from_ast(prog.function))


class Function(BaseModel):
    name: str
    instructions: "list[Instruction]"
    return_type: parser.CType

    @staticmethod
    def from_ast(ast: parser.Function):
        return Function(
            name=ast.name.root,
            return_type=ast.return_type,
            instructions=return_to_tacky(ast.body.root),
        )


type Instruction = (
    Return | Unary | BinaryOp | Copy | Jump | JumpIfZero | JumpIfNotZero | Label
)
type Value = parser.Constant | Var


class Return(BaseModel):
    root: Value


class Var(BaseModel):
    name: str


type Simple_Unary = t.Literal["COMPLEMENT", "MINUS"]
type Unary_Op = Simple_Unary | t.Literal["NOT"]


class Unary(BaseModel):
    operation: Unary_Op
    source: Value
    destination: Value


class BinaryOp(BaseModel):
    operation: parser.Binary_Operation
    src1: Value
    src2: Value
    dest: Value


class Copy(BaseModel):
    src: Value
    dest: Value


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


# Evident how we can convert other types of statements (like an if)
def return_to_tacky(ret: parser.ReturnStatement):
    instructions: list[Instruction] = []
    final = emit_tacky(ret.exp, instructions)
    return instructions + [Return(root=final)]


_temp_var_counter = -1
_label_counter = -1


def emit_tacky(
    exp: parser.Expression,
    instructions: list[Instruction] | None,
) -> Value:
    """
    Mutates instructions (if they exist)
    """
    instructions = [] if instructions is None else instructions

    def make_temp(label: str = "_TMP_"):
        global _temp_var_counter
        _temp_var_counter += 1
        return f"{label}-{_temp_var_counter}"

    def make_label(label: str):
        global _label_counter
        _label_counter += 1
        return f"{label}.{_label_counter}"

    match exp.type:
        case parser.Factor(type=type):
            match type:
                case parser.Constant():
                    return type
                case parser.Unary(type=operation, exp=factor):
                    source = emit_tacky(parser.Expression(type=factor), instructions)
                    destination = Var(name=make_temp())
                    instructions.append(
                        Unary(
                            operation=operation,
                            source=source,
                            destination=destination,
                        )
                    )
                    return destination
                case parser.Expression():
                    return emit_tacky(type, instructions)
        case parser.BinaryOp(type=bin_op, lhs=lhs, rhs=rhs):
            match bin_op:
                case "AND":
                    end = make_label("and_end")
                    dst = Var(name=make_temp("result_and"))

                    instructions.append(Copy(src=parser.Constant(root=0), dest=dst))

                    v1 = emit_tacky(lhs, instructions)
                    instructions.append(JumpIfZero(condition=v1, target=end))
                    v2 = emit_tacky(rhs, instructions)
                    instructions.extend(
                        (
                            JumpIfZero(condition=v2, target=end),
                            # Both passed!
                            Copy(src=parser.Constant(root=1), dest=dst),
                            Label(identifier=end),
                        )
                    )
                    return dst
                case "OR":
                    end = make_label("and_end")
                    dst = Var(name=make_temp("result_or"))

                    instructions.append(Copy(src=parser.Constant(root=1), dest=dst))

                    v1 = emit_tacky(lhs, instructions)
                    # If v1 is not zero then exit
                    # We already set the return to 1
                    instructions.append(JumpIfNotZero(condition=v1, target=end))
                    v2 = emit_tacky(rhs, instructions)

                    instructions.extend(
                        (
                            JumpIfNotZero(condition=v2, target=end),
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
