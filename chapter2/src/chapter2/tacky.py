import typing as t

from chapter2 import parser

from pydantic import BaseModel


class Program(BaseModel):
    function_def: Function

    @staticmethod
    def from_ast(prog: parser.Program):
        return Program(function_def=Function.from_ast(prog.function))


class Function(BaseModel):
    name: str
    instructions: list[Instruction]
    return_type: parser.CType

    @staticmethod
    def from_ast(ast: parser.Function):
        if not isinstance(ast.body.root, parser.ReturnStatement):
            raise NotImplementedError("Nope!")

        return Function(
            name=ast.name.root,
            return_type=ast.return_type,
            instructions=return_to_tacky(ast.body.root),
        )


type Instruction = Return | Unary
type Value = parser.Constant | Var


class Return(BaseModel):
    root: Value


class Var(BaseModel):
    name: str


class Unary(BaseModel):
    operation: t.Literal["COMPLEMENT", "NEGATION"]
    source: Value
    destination: Value


# Evident how we can convert other types of statements (like an if)
def return_to_tacky(ret: parser.ReturnStatement):
    instructions: list[Instruction] = []
    final = emit_tacky(ret.exp, instructions)
    return [*instructions, Return(root=final)]


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
        case parser.Constant():
            return exp.type
        case parser.Unary(type=operation, exp=exp):
            source = emit_tacky(exp, instructions)
            destination = Var(name=make_temp())
            instructions.append(
                Unary(
                    operation=operation,
                    source=source,
                    destination=destination,
                )
            )
            return destination
