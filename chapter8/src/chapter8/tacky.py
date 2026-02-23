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

Tacky for if statements

```
<instructions for condition>
c = <result of condition>
JumpIfZero(c, end)
<instructions for statement>
Label(end)
```

For if-else

```
<instructions for condition>
c = <result of condition>
JumpIfZero(c, else_label)
<instructions for statement1>
Jump(end)
Label(else_label)
<instructions for statement2>
Label(end)
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

from chapter8 import parser, semantic_analysis
from shared import data_types as dt
from shared import pure_functions as pf


def emit_tacky(
    block: parser.Expression | parser.Block_Item,
    instructions: list[Instruction],
) -> Value | None:
    """
    Mutates instructions
    """

    match block:
        case parser.Expression():
            return emit_exp(block, instructions)
        case parser.Statement():
            return _match_statement(block, instructions)
        case parser.Declaration(name=name, init=init):
            var = Var(name=name.root)
            if init:
                result = emit_exp(init, instructions)
                instructions.append(Copy(src=result, dest=var))
            return var


def _match_statement(stmt: parser.Statement, instructions: list[Instruction]) -> None:
    match stmt.root:
        case parser.Block(body=body):
            for line in body:
                _ = emit_tacky(line, instructions)
        case parser.ReturnStatement(exp=expression):
            final = emit_exp(expression, instructions)
            instructions.append(Return(root=final))
        case parser.Expression():
            _ = emit_exp(stmt.root, instructions)
        case parser.IfStatement(condition=condition, then=then, else_s=None):
            _ = do_an_if(
                condition,
                then,
                instructions,
                store_result=False,
            )
        case parser.IfStatement(condition=condition, then=then, else_s=else_s):
            _ = do_an_if_else(
                condition,
                then,
                else_s,  # pyright: ignore[reportArgumentType]
                instructions,
                store_result=False,
            )
        case parser.Goto(label=label):
            instructions.append(Jump(target=label.root.replace("`", "")))
        case parser.Label(label=label, statement=inner):
            instructions.append(Label(identifier=label.root.replace("`", "")))
            _match_statement(inner, instructions)
        case "nope":
            return None


def emit_exp(
    exp: parser.Expression | parser.Factor,
    instructions: list[Instruction],
) -> Value:
    match exp.type:
        case parser.Factor() | parser.Expression():
            return emit_exp(exp.type, instructions)

        case parser.Identifier(root=name):
            return Var(name=name)
        case parser.Constant():
            return exp.type
        case parser.Unary():
            return _emit_unary(exp.type, instructions)

        case parser.FancyAssignment():
            raise ValueError("Should have been gone by this stage!")

        case parser.Conditional(left=left, middle=middle, right=right):
            cond_val = do_an_if_else(
                left, middle, right, instructions, store_result=True
            )
            assert cond_val, "NOPE"
            return cond_val

        case parser.NormalAssigment(lhs=lhs, rhs=rhs):
            match lhs:
                case (
                    parser.Identifier(root=name)
                    | parser.Expression(
                        type=parser.Factor(type=parser.Identifier(root=name))
                    )
                ):
                    return emit_copy_exp(Var(name=name), rhs, instructions)
                case _:
                    raise ValueError("NOPE! Bad assignment")
        case parser.BinaryOp():
            return _emit_binop(exp.type, instructions)


def _emit_unary(unary_op: parser.Unary, instructions: list[Instruction]) -> Value:
    """
    Unary operations are a PITA.
    Mostly because of those darned `++` and `--` operators!
    The devil himself came up with them.
    """
    operation, factor, pre = unary_op.type, unary_op.exp, unary_op.pre
    destination: Value

    source = emit_exp(factor, instructions)

    if operation not in ("++", "--"):
        destination = Var(name=_make_temp())
        instructions.append(
            Unary(
                operation=operation,
                source=source,
                destination=destination,
            )
        )
        return destination

    # The expression itself has already been evaluaded up top
    current: t.Any = factor
    while not isinstance(current, parser.Identifier):
        match factor.type:
            case parser.Identifier():
                current = factor.type
            case parser.Unary():
                # This is MEGA jank!
                # It's here because `~(a)++` is assignable...
                # So is ~~~!!!a++ (so on and so forth)
                # I'm 1000% sure this is wrong, but we hadn't learned operators properly up until then
                # I CAN'T wait to get rid of these silly nerds.
                factor = factor.type.exp
                current = factor.type
            case _:
                raise ValueError("Not assignable????")

    assert isinstance(current, parser.Identifier), f"{current} is not assignable!"

    # Note - at this stage this factor _MUST_ be an lvalue
    # Semantic analysis handles that for us
    lhs = parser.Expression(type=factor)
    rhs = parser.Expression(type=parser.Factor(type=parser.Constant(root=1)))
    intermediate_exp = parser.Expression(
        type=parser.BinaryOp(
            type="PLUS" if operation == "++" else "MINUS",
            lhs=lhs,
            rhs=rhs,
        )
    )

    if pre:
        return emit_copy_exp(Var(name=current.root), intermediate_exp, instructions)

    destination = Var(name=_make_temp())
    instructions.append(Copy(src=source, dest=destination))
    _ = emit_copy_exp(Var(name=current.root), intermediate_exp, instructions)
    return destination


def _emit_binop(op: parser.BinaryOp, instructions: list[Instruction]):
    bin_op, lhs, rhs = op.type, op.lhs, op.rhs
    match bin_op:
        case "AND":
            end = _make_label("and_end")
            dst = Var(name=_make_temp("result_and"))
            tmp = Var(name=_make_temp("tmp"))

            # DON'T use `extend` for the whole thing!
            # The instructions will be appendded out of order!
            # As the inner `emit_tacky` will "win"
            instructions.append(Copy(src=parser.Constant(root=0), dest=dst))
            res_lhs = emit_exp(lhs, instructions)
            instructions.extend(
                (
                    Copy(src=res_lhs, dest=tmp),
                    JumpIfZero(condition=tmp, target=end),
                )
            )
            res_rhs = emit_exp(rhs, instructions)
            instructions.extend(
                (
                    Copy(src=res_rhs, dest=tmp),
                    JumpIfZero(condition=tmp, target=end),
                    Copy(src=parser.Constant(root=1), dest=dst),
                    Label(identifier=end),
                ),
            )
            return dst
        case "OR":
            end = _make_label("or_end")
            dst = Var(name=_make_temp("result_or"))
            tmp = Var(name=_make_temp("tmp"))

            instructions.append(Copy(src=parser.Constant(root=1), dest=dst))
            res_lhs = emit_exp(lhs, instructions)
            instructions.extend(
                (
                    Copy(src=res_lhs, dest=tmp),
                    # If lhs is not zero then exit
                    # We already set the return to 1
                    JumpIfNotZero(condition=tmp, target=end),
                )
            )

            res_rhs = emit_exp(rhs, instructions)
            instructions.extend(
                (
                    Copy(src=res_rhs, dest=tmp),
                    JumpIfNotZero(condition=tmp, target=end),
                    Copy(src=parser.Constant(root=0), dest=dst),
                    Label(identifier=end),
                )
            )

            return dst
        case _:
            v1 = emit_exp(lhs, instructions)
            v2 = emit_exp(rhs, instructions)
            dst = Var(name=_make_temp("_tmp_bin_op_result"))
            instructions.append(BinaryOp(operation=bin_op, src1=v1, src2=v2, dest=dst))
            return dst


def do_an_if(
    condition: parser.Expression,
    then: parser.Statement | parser.Expression,
    instructions: list[Instruction],
    *,
    store_result: bool,
):
    condition_result = Var(name=_make_temp("condition_result"))
    result_var = Var(name=_make_temp("result_var")) if store_result else None
    end_label = _make_label("end")

    c = emit_exp(condition, instructions)
    instructions.append(Copy(src=c, dest=condition_result))

    def store_the_res(res: Value | None):
        assert res is not None and result_var is not None, "Weeeeeeeeeird"
        instructions.append(Copy(src=res, dest=result_var))

    instructions.append(JumpIfZero(condition=condition_result, target=end_label))
    res = emit_tacky(
        then,
        instructions,
    )
    if store_result:
        store_the_res(res)

    instructions.append(Label(identifier=end_label))

    return result_var


def do_an_if_else(
    condition: parser.Expression,
    then: parser.Statement | parser.Expression,
    else_s: parser.Statement | parser.Expression,
    instructions: list[Instruction],
    *,
    store_result: bool,
):
    condition_result = Var(name=_make_temp("condition_result"))
    result_var = Var(name=_make_temp("result_var")) if store_result else None
    else_label = _make_label("else_label")
    end_label = _make_label("end")

    def store_the_res(res: Value | None):
        assert res is not None and result_var is not None, "Weeeeeeeeeird"
        instructions.append(Copy(src=res, dest=result_var))

    c = emit_exp(condition, instructions)
    instructions.append(Copy(src=c, dest=condition_result))

    instructions.append(JumpIfZero(condition=condition_result, target=else_label))
    res = emit_tacky(
        then,
        instructions,
    )

    if store_result:
        store_the_res(res)

    instructions.extend(
        [
            Jump(target=end_label),
            Label(identifier=else_label),
        ]
    )
    res = emit_tacky(
        else_s,
        instructions,
    )
    if store_result:
        store_the_res(res)
    instructions.append(Label(identifier=end_label))

    return result_var


def emit_copy_exp(var: Var, exp: parser.Expression, instructions: list[Instruction]):
    res = emit_exp(exp, instructions)
    instructions.append(Copy(src=res, dest=var))
    return var


def _make_temp(label: str = "_TMP_"):
    semantic_analysis.Global_Counter += 1
    return f"{label}-{semantic_analysis.Global_Counter}"


def _make_label(label: str):
    semantic_analysis.Global_Counter += 1
    return f"{label}.{semantic_analysis.Global_Counter}"


class Program(BaseModel):
    function_def: "Function"

    @staticmethod
    def from_ast(prog: parser.Program):
        instructions: list[Instruction] = []
        return Program(function_def=Function.from_ast(prog.function, instructions))

    @t.override
    def __str__(self):
        return str(self.function_def)


class Function(BaseModel):
    name: str
    instructions: "list[Instruction]"
    return_type: parser.CType

    @staticmethod
    def from_ast(ast: parser.Function, instructions: list[Instruction]):
        for line in ast.body.body:
            _ = emit_tacky(line, instructions)
        return Function(
            name=ast.name.root,
            return_type=ast.return_type,
            instructions=instructions,
        )

    @t.override
    def __str__(self):
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
            body = pf.indent("\n".join(str(b) for b in self.instructions))

        return f"{start}{body})"


type Instruction = (
    Return | Unary | BinaryOp | Copy | Jump | JumpIfZero | JumpIfNotZero | Label
)
type Value = parser.Constant | Var


class Return(BaseModel):
    root: Value | None

    @t.override
    def __str__(self):
        return f"(return {str(self.root)})"


class Var(BaseModel):
    name: str

    @t.override
    def __str__(self):
        return f"`{self.name}`"


type Simple_Unary = t.Literal["COMPLEMENT", "MINUS"]
type Unary_Op = Simple_Unary | t.Literal["NOT"]


class Unary(BaseModel):
    operation: Unary_Op
    source: Value
    destination: Value

    @t.override
    def __str__(self):
        return f"({self.operation} {str(self.source)} {str(self.destination)})"


class BinaryOp(BaseModel):
    operation: parser.Binary_Operation
    src1: Value
    src2: Value
    dest: Value

    @t.override
    def __str__(self):
        return f"({self.operation} {str(self.src1)} {str(self.src2)})\n({self.operation} {str(self.src2)} {str(self.dest)})"


class Copy(BaseModel):
    src: Value
    dest: Value

    @t.override
    def __str__(self):
        return f"(copy {str(self.src)} {str(self.dest)})"


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
