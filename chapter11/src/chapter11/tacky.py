"""
underscore denotes new shit

```
program = Program(top_level*)
top_level = Function(identifier, bool global, identifier* params, instruction* body)
          | StaticVariable(identifier, bool global, _type t, static_init init_)
instruction = Return(val)
            | _SignExtend(val src, val dst)_
            | _Truncate(val src, val dst)_
            | Unary(unary_operator, val src, val dst)
            | Binary(binary_operator, val src1, val src2, val dst)
            | Copy(val src, val dst)
            | Jump(identifier target)
            | JumpIfZero(val condition, identifier target)
            | JumpIfNotZero(val condition, identifier target)
            | Label(identifier)
            | FunCall(identifier fun_name, val* args, val dst)
val = Constant(const) | Var(identifier)
unary_operator = Complement | Negate | Not
binary_operator = Add | Subtract | Multiply | Divide | Remainder | Equal | NotEqual
                | LessThan | LessOrEqual | GreaterThan | GreaterOrEqual
```
"""

import typing as t
from textwrap import dedent

from pydantic import BaseModel, BeforeValidator

from chapter11 import parser, semantic_analysis
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
        case parser.Function_Declaration():
            decl = Function_Definition.from_ast(block)
            assert decl is None, "There should be no body here man!"
            return
        case parser.Expression():
            return emit_exp(block, instructions)
        case parser.Statement():
            return _match_statement(block, instructions)
        case parser.Variable_Declaration(name=name, init=init):
            var = Var(name=name.root)
            if var.is_static():
                return var
            if init:
                result = emit_exp(init, instructions)
                instructions.append(Copy(src=result, dest=var))
            return var


def _match_statement(stmt: parser.Statement, instructions: list[Instruction]) -> None:
    match stmt.root:
        case parser.SwitchCase(label=label, body=body):
            instructions.append(Label(identifier=label.root))
            _match_statement(body, instructions)
        case parser.Switch(
            checker=checker,
            associated_cases=associated_cases,
            body=body,
            control_label=control_label,
        ):
            checker_res = emit_exp(checker, instructions)
            if isinstance(checker_res, Var):
                checker_expr = parser.Expression.read_var(
                    checker_res.name, type=checker.type
                )
            else:
                checker_expr = parser.Expression(
                    root=parser.Factor(root=checker_res, type=checker.type),
                    type=checker.type,
                )

            end_of_switch_label = Label.from_break(control_label)
            # By default we jump to where a `break` would jump to if none of our
            # cases eval to true
            final_jump = parser.Identifier(end_of_switch_label.identifier)

            for case in associated_cases:
                if isinstance(case.type, parser.SwitchCase.Default):
                    # UNLESS - we find a default.
                    # Note that semantic-analysis ensures that there's
                    final_jump = case.label
                    continue

                goto = parser.Statement(root=parser.Goto(label=case.label))
                _ = do_an_if(
                    parser.Expression(
                        type=parser.CType(root="int"),
                        root=parser.BinaryOp(
                            op="==", lhs=checker_expr, rhs=case.type.check
                        ),
                    ),
                    goto,
                    instructions,
                    store_result=False,
                )

            # We always put the goto-default at the end
            # This way if any of the previous ifs cocked up we can just go here
            _match_statement(
                parser.Statement(root=parser.Goto(label=final_jump)),
                instructions,
            )
            _match_statement(body, instructions)
            # We don't forget to add the control_label at the end
            # (Otherwise `break` wouldn't do nothin')
            instructions.append(end_of_switch_label)

        case parser.DoWhile(
            condition=condition, body=body, control_label=control_label
        ):
            start_label = Label(identifier=control_label)
            instructions.append(start_label)
            _ = emit_tacky(body, instructions)
            instructions.append(Label.from_continue(control_label))

            condition_result = emit_exp(condition, instructions)
            instructions.extend(
                (
                    JumpIfNotZero(condition=condition_result, target=start_label),
                    Label.from_break(control_label),
                )
            )

        case parser.While(condition=condition, body=body, control_label=control_label):
            continue_label = Label.from_continue(control_label)
            break_label = Label.from_break(control_label)
            instructions.append(continue_label)
            condition_result = emit_exp(condition, instructions)
            instructions.append(
                JumpIfZero(condition=condition_result, target=break_label)
            )
            _ = emit_tacky(body, instructions)
            instructions.extend(
                (
                    Jump(target=continue_label),
                    break_label,
                )
            )

        case parser.For(
            init=init,
            condition=condition,
            post=post,
            body=body,
            control_label=control_label,
        ):
            if init:
                _ = emit_tacky(init, instructions)
            start_label = Label(identifier=control_label)
            instructions.append(start_label)
            continue_label = Label.from_continue(control_label)
            break_label = Label.from_break(control_label)
            if condition:
                condition_result = emit_exp(condition, instructions)
                instructions.append(
                    JumpIfZero(condition=condition_result, target=break_label)
                )
            # From the book:
            # If it [the condition] is absent, the C standard says that this
            # expression is “replaced by a nonzero constant” (section 6.8.5.3,
            # paragraph 2)
            # But the book also says that we can ignore that shit
            # // else:
            # //   instructions.append(
            # //      JumpIfZero(condition=parser.Constant(1), target=break_label)
            # //   )
            _ = emit_tacky(body, instructions)
            instructions.append(continue_label)
            if post:
                _ = emit_exp(post, instructions)
            instructions.extend(
                (
                    Jump(target=start_label),
                    break_label,
                )
            )
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
            instructions.append(Jump(target=pf.to_valid_c_name(label.root)))
        case parser.Label(label=label, statement=inner):
            instructions.append(Label(identifier=pf.to_valid_c_name(label.root)))
            _match_statement(inner, instructions)
        case parser.Continue(control_label=control_label):
            instructions.append(Jump(target=Label.from_continue(control_label)))
        case parser.Break(control_label=control_label):
            instructions.append(Jump(target=Label.from_break(control_label)))
        case "nope":
            return None


def emit_exp(
    exp: parser.Expression | parser.Factor,
    instructions: list[Instruction],
) -> Value:
    match exp.root:
        case parser.Func_Call():
            return emit_func_call(exp.root, instructions)
        case parser.Cast(target_type=target_type, exp=inner):
            res = emit_exp(inner, instructions)
            if target_type == inner.type:
                return res
            destination = Var.new(type=inner.type)
            inst: Instruction
            if target_type.root == parser.CType(root="long"):
                inst = SignExtend(src=res, dest=destination)
            else:
                inst = Truncate(src=res, dest=destination)
            instructions.append(inst)
            return destination
        case parser.Factor() | parser.Expression():
            return emit_exp(exp.root, instructions)

        case parser.Identifier(root=name):
            return Var.new(type=exp.type, name=name)
        case parser.Constant():
            return exp.root
        case parser.Unary():
            return _emit_unary(exp.root, instructions)

        case parser.Fancy_Assignment():
            raise ValueError("Should have been gone by this stage!")

        case parser.Conditional(left=left, middle=middle, right=right):
            cond_val = do_an_if_else(
                left, middle, right, instructions, store_result=True
            )
            assert cond_val, "NOPE"
            return cond_val

        case parser.Normal_Assignment(lhs=lhs, rhs=rhs):
            match lhs:
                case (
                    parser.Identifier(root=name)
                    | parser.Expression(
                        root=parser.Factor(root=parser.Identifier(root=name))
                    )
                ):
                    return emit_copy_exp(
                        Var.new(type=exp.type, name=name), rhs, instructions
                    )
                case _:
                    raise ValueError("NOPE! Bad assignment")
        case parser.BinaryOp():
            return _emit_binop(exp.root, exp.type, instructions)


def _emit_unary(unary_op: parser.Unary, instructions: list[Instruction]) -> Value:
    """
    Unary operations are a PITA.
    Mostly because of those darned `++` and `--` operators!
    The devil himself came up with them.
    """
    operation, factor, pre, type = (
        unary_op.op,
        unary_op.exp,
        unary_op.pre,
        unary_op.exp.type,
    )
    destination: Value

    source = emit_exp(factor, instructions)

    type = parser.CType.assert_is_trivial(type)

    if operation not in ("++", "--"):
        destination = Var.new(type=type)
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
        match factor.root:
            case parser.Identifier():
                current = factor.root
            case parser.Unary():
                # This is MEGA jank!
                # It's here because `~(a)++` is assignable...
                # So is ~~~!!!a++ (so on and so forth)
                # I'm 1000% sure this is wrong, but we hadn't learned operators properly up until then
                # I CAN'T wait to get rid of these silly nerds.
                factor = factor.root.exp
                current = factor.root
            case _:
                raise ValueError("Not assignable????")

    assert isinstance(current, parser.Identifier), f"{current} is not assignable!"

    # Note - at this stage this factor _MUST_ be an lvalue
    # Semantic analysis handles that for us
    lhs = parser.Expression(root=factor, type=type)
    rhs = parser.Expression(
        root=parser.Factor(root=parser.Constant(root=1, ctype=type), type=type),
        type=type,
    )
    intermediate_exp = parser.Expression(
        type=type,
        root=parser.BinaryOp(
            op="PLUS" if operation == "++" else "MINUS",
            lhs=lhs,
            rhs=rhs,
        ),
    )

    if pre:
        return emit_copy_exp(
            Var.new(type=type, name=current.root), intermediate_exp, instructions
        )

    destination = Var.new(type=type)
    instructions.append(Copy(src=source, dest=destination))
    _ = emit_copy_exp(
        Var.new(type=type, name=current.root), intermediate_exp, instructions
    )
    return destination


def _emit_binop(
    op: parser.BinaryOp, type: parser.CType | None, instructions: list[Instruction]
):
    bin_op, lhs, rhs = op.op, op.lhs, op.rhs
    type = parser.CType.assert_is_trivial(type)
    match bin_op:
        case "AND":
            end = _make_label("and_end")
            dst = Var.new(type=type, name=_make_temp("result_and"))
            tmp = Var.new(type=type, name=_make_temp("tmp"))

            # DON'T use `extend` for the whole thing!
            # The instructions will be appendded out of order!
            # As the inner `emit_tacky` will "win"
            instructions.append(Copy(src=parser.Constant.from_bool(0), dest=dst))
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
                    Copy(src=parser.Constant.from_bool(1), dest=dst),
                    Label(identifier=end),
                ),
            )
            return dst
        case "OR":
            end = _make_label("or_end")
            dst = Var(name=_make_temp("result_or"))
            tmp = Var(name=_make_temp("tmp"))

            instructions.append(Copy(src=parser.Constant.from_bool(1), dest=dst))
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
                    Copy(src=parser.Constant.from_bool(0), dest=dst),
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
    condition: parser.Expression | Value,
    then: parser.Statement | parser.Expression,
    instructions: list[Instruction],
    *,
    store_result: bool,
):
    """
    For convenience - also accepts some `Value` so we can re-use previous calculations
    """
    match condition:
        case parser.Constant() | Var():
            condition_result = condition
        case parser.Expression():
            condition_result = Var(name=_make_temp("condition_result"))
            c = emit_exp(condition, instructions)
            instructions.append(Copy(src=c, dest=condition_result))
    result_var = Var(name=_make_temp("result_var")) if store_result else None
    end_label = _make_label("end")

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


def emit_func_call(func: parser.Func_Call, instructions: list[Instruction]) -> Value:
    name = pf.to_valid_c_name(func.name.root)
    args = [emit_exp(i, instructions) for i in func.args]
    dest = Var(name=_make_temp())
    instructions.append(
        Func_Call(
            name=name,
            args=args,
            dest=dest,
        )
    )

    return dest


def _make_temp(label: str = "_TMP_"):
    semantic_analysis.Global_Counter += 1
    return f"{label}-{semantic_analysis.Global_Counter}"


def _make_label(label: str):
    semantic_analysis.Global_Counter += 1
    return f"{label}.{semantic_analysis.Global_Counter}"


type Valid_Identifier = t.Annotated[dt.Identifier, BeforeValidator(pf.to_valid_c_name)]


class Program(BaseModel):
    function_defs: list[Function_Definition]
    static_vars: list[Static_Variable]

    @staticmethod
    def from_ast(prog: parser.Program):
        res = Program(function_defs=[], static_vars=[])
        symbol_table = semantic_analysis.SYMBOL_TABLE.get()
        for decl in prog.declarations:
            match decl:
                case parser.Function_Declaration():
                    func = Function_Definition.from_ast(decl)
                    if func:
                        res.function_defs.append(func)
                case parser.Variable_Declaration():
                    # Handled later
                    pass

        for key, symbol in symbol_table.data.items():
            decl = Static_Variable.from_symbol(key, symbol)
            if decl:
                res.static_vars.append(decl)
        return res

    @t.override
    def __str__(self):
        return "\n".join(map(str, self.static_vars + self.function_defs))


class Static_Variable(BaseModel):
    name: Valid_Identifier
    is_global: bool
    init: semantic_analysis.Symbol_Table.Static.StaticInit
    type: parser.TrivialType

    @staticmethod
    def from_symbol(name: str, symbol: semantic_analysis.Symbol_Table.Symbol):
        if not isinstance(symbol, semantic_analysis.Symbol_Table.Static):
            # Don't care
            return None

        res = Static_Variable(
            name=name,
            is_global=symbol.is_global,
            type=symbol.type,
            init=semantic_analysis.Symbol_Table.Static.StaticInit(val=0),
        )

        match symbol.initial_value:
            case "tentative":
                # Initialized to zero
                return res
            case semantic_analysis.Symbol_Table.Static.StaticInit(val=val):
                res.init.val = val
                return res
            case "Nope!":
                # The linker will yell at us later if it's not found
                return

    @t.override
    def __str__(self):
        return f"(let{'-global' if self.is_global else ''} (= `{self.name}:{self.type}` {self.init}))"


class Function_Definition(BaseModel):
    name: Valid_Identifier
    params: list[tuple[Var, parser.CType]]
    instructions: list[Instruction]
    return_type: parser.CType
    is_global: bool

    @staticmethod
    def from_ast(ast: parser.Function_Declaration):
        if not ast.body:
            return
        # Note: each function has it's own list of instructions
        body: list[Instruction] = []
        for line in ast.body.body:
            _ = emit_tacky(line, body)
        symbol_table = semantic_analysis.SYMBOL_TABLE.get()
        symbol = symbol_table.data[ast.name.root]
        assert isinstance(symbol, semantic_analysis.Symbol_Table.Func), "Compiler bug!"
        params = [
            (Var(name=id.root), type)
            for (id, type) in zip(ast.param_list, ast.type.params, strict=True)
        ]
        return Function_Definition(
            params=params,
            name=ast.name.root,
            return_type=ast.type.return_type,
            instructions=body,
            is_global=symbol.is_global,
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


class Func_Call(BaseModel):
    name: Valid_Identifier
    args: list[Value]
    dest: Var

    @t.override
    def __str__(self):
        return f"(= {self.dest} ({self.name} {' '.join(map(str, self.args) if self.args else '()')})"  # )


type Instruction = (
    Return
    | Unary
    | BinaryOp
    | Copy
    | Jump
    | JumpIfZero
    | JumpIfNotZero
    | Label
    | Func_Call
    | SignExtend
    | Truncate
)
type Value = parser.Constant | Var


class Return(BaseModel):
    root: Value | None

    @t.override
    def __str__(self):
        return f"(return {self.root!s})"


class Var(BaseModel):
    name: str

    @staticmethod
    def new(type: parser.CType | None, name: str | None = None):
        type = parser.CType.assert_is_trivial(type)
        if name is None:
            name = _make_temp()
        res = Var(name=name)
        if (
            res.is_static()
        ):  # Note: That this will never be true if we give it a "correct" name!
            assert semantic_analysis.SYMBOL_TABLE.get().data[name].type == type
            return res
        semantic_analysis.SYMBOL_TABLE.get().data[name] = (
            semantic_analysis.Symbol_Table.Local(type=type)
        )
        return res

    def is_static(self):
        symbol_table = semantic_analysis.SYMBOL_TABLE.get()
        if self.name not in symbol_table:
            # It's an auto-local
            return False
        return isinstance(
            symbol_table.data[self.name], semantic_analysis.Symbol_Table.Static
        )

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
        return f"({self.operation} {self.source!s} {self.destination!s})"


class BinaryOp(BaseModel):
    operation: parser.Binary_Operation
    src1: Value
    src2: Value
    dest: Value

    @t.override
    def __str__(self):
        return f"(copy ({self.operation} {self.src1!s} {self.src2!s}) {self.dest!s})"


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

    # Note the order, we want to first match to `Label` and THEN try to convert
    # it to a `Valid_Identifier`
    # Otherwise the `Valid_Identifier` will crash out
    target: Label | Valid_Identifier

    @t.override
    def __str__(self):
        return f"(jump {self.target})"


class JumpIfZero(Jump):
    condition: Value

    @t.override
    def __str__(self):
        return f"(jump {self.target} (== {self.condition} 0))"


class JumpIfNotZero(Jump):
    condition: Value

    @t.override
    def __str__(self):
        return f"(jump {self.target} (!= {self.condition} 0))"


class Label(BaseModel):
    identifier: Valid_Identifier

    @staticmethod
    def from_break(label: str):
        return Label(identifier=f"break_{pf.to_valid_c_name(label)}")

    @staticmethod
    def from_continue(label: str):
        return Label(identifier=f"continue_{pf.to_valid_c_name(label)}")

    @t.override
    def __str__(self):
        return f"(label: {self.identifier})"


class SrcDest(BaseModel):
    src: Value
    dest: Value


class SignExtend(SrcDest):
    @t.override
    def __str__(self):
        return f"(sign-extend {self.src!s} {self.dest!s})"


class Truncate(SrcDest):
    @t.override
    def __str__(self):
        return f"(truncate {self.src!s} {self.dest!s})"


class Copy(SrcDest):
    @t.override
    def __str__(self):
        return f"(copy {self.src!s} {self.dest!s})"
