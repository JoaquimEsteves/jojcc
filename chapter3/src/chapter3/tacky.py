"""
underscore denotes new shit

```
program = Program(function_definition)
function_definition = Function(identifier, instruction* body)
instruction = Return(val)
            | Unary(unary_operator, val src, val dst)
            | _Binary(binary_operator, val src1, val src2, val dst)_
val = Constant(int) | Var(identifier)
unary_operator = Complement | Negate
_binary_operator_ = Add | Subtract | Multiply | Divide | Remainder
```
"""

import typing as t

from chapter3 import parser

from pydantic import BaseModel


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


type Instruction = Return | Unary | BinaryOp
type Value = parser.Constant | Var


class Return(BaseModel):
    root: Value


class Var(BaseModel):
    name: str


class Unary(BaseModel):
    operation: t.Literal["COMPLEMENT", "MINUS"]
    source: Value
    destination: Value


class BinaryOp(BaseModel):
    operation: parser.Binary_Operation
    src1: Value
    src2: Value
    dest: Value


# Evident how we can convert other types of statements (like an if)
def return_to_tacky(ret: parser.ReturnStatement):
    instructions: list[Instruction] = []
    final = emit_tacky(ret.exp, instructions)
    return instructions + [Return(root=final)]


_counter = -1


def emit_tacky(
    exp: parser.Expression,
    instructions: list[Instruction] | None,
) -> Value:
    instructions = [] if instructions is None else instructions

    def make_temp():
        global _counter
        _counter += 1
        return f"_TMP-{_counter}"

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
            v1 = emit_tacky(lhs, instructions)
            v2 = emit_tacky(rhs, instructions)
            dst = Var(name=make_temp())
            instructions.append(BinaryOp(operation=bin_op, src1=v1, src2=v2, dest=dst))
            return dst
