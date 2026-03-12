import typing as t
from contextlib import suppress
from contextvars import ContextVar

from pydantic import BaseModel

import chapter8.parser as parser
from shared import pure_functions as pf

Global_Counter: int = 0
"""
Will be used during tacky as well.
This is to ensure that the tacky-boys don't somehow end up using the same
name as this one.
"""


class Variable_Map(BaseModel):
    data: dict[str, MapEntry] = {}

    class MapEntry(BaseModel):
        """
        Simply informs us if we can declare an item or not.
        Example:

        ```c
        int foo = 1;
        {
            int foo = 2; // valid!
        }
        int foo = 2; // NOT VALID!
        ```
        """

        name: str
        from_current_block: bool = True

    def valid_declaration(self, name: str):
        if name not in self.data:
            return True
        return not self.data[name].from_current_block

    def __getitem__(self, name: str):
        entry = self.data.get(name)
        return entry.name if entry else None

    def get_new_name(self, original: str, *, valid_c: bool = False):
        new_name = _get_new_name(original, valid_c=valid_c)
        self.data[original] = Variable_Map.MapEntry(name=new_name)

        return new_name

    def get_copy(self):
        return Variable_Map(
            data={
                key: Variable_Map.MapEntry(name=val.name, from_current_block=False)
                for key, val in self.data.items()
            },
        )


class Label_Map(BaseModel):
    """
    Labels (unlike variable declarations) are quite simple.
    Labels are unique per file. Simple as
    """

    data: dict[str, str] = {}

    def valid_declaration(self, name: str):
        return name not in self.data

    def __getitem__(self, name: str):
        return self.data.get(name)

    def get_new_name(self, original: str, *, valid_c: bool = False):
        new_name = _get_new_name(original, valid_c=valid_c)
        self.data[original] = new_name

        return new_name


###############################################################################
#                                                                             #
#                                Context Vars                                 #
#                                                                             #
###############################################################################
# They're globals with a cute little bow on top.
# The advantage is that using the `set_context` function
# we can have them be scoped trivially without a *BUNCH* of prop-drilling.
VARIABLE_MAP = ContextVar("VARIABLE_MAP ", default=Variable_Map())
LABEL_MAP = ContextVar("LABEL_MAP ", default=Label_Map())
SWITCH_CONTROL_LABEL = ContextVar("SWITCH_CONTROL_LABEL ", default="")
LOOP_CONTROL_LABEL = ContextVar("LOOP_CONTROL_LABEL ", default="")
FOUND_CASES: ContextVar[dict[str, parser.SwitchCase]] = ContextVar(
    "FOUND_CASES", default={}
)
MOST_RECENT_CONTROL_LABEL: ContextVar[ContextVar[str] | None] = ContextVar(
    "MOST_RECENT ", default=None
)
"""
Where do those damn breaks apply to
"""


def get_control_label(type: t.Literal["all", "loop", "switch"] = "all"):
    match type:
        case "all":
            with suppress(AttributeError):
                return MOST_RECENT_CONTROL_LABEL.get().get()  # pyright: ignore[reportOptionalMemberAccess]
            return None
        case "loop":
            return LOOP_CONTROL_LABEL.get() or None
        case "switch":
            return SWITCH_CONTROL_LABEL.get() or None


def resolve_program(prog: parser.Program):
    func = prog.function
    with pf.set_context(VARIABLE_MAP, VARIABLE_MAP.get().get_copy()):
        new_blocks = resolve_block(func.body)
    _ = check_labels_in_program(new_blocks.body)

    if func.return_type.root == "int":
        # Ensures that there's always a return statement at the end
        new_blocks.body.append(
            parser.Statement(
                root=parser.ReturnStatement(
                    exp=parser.Expression(type=parser.Factor(type=parser.Constant(0)))
                )
            )
        )

    return parser.Program(
        function=parser.Function(
            name=func.name,
            return_type=func.return_type,
            body=new_blocks,
        )
    )


def resolve_block(body: parser.Block) -> parser.Block:
    return parser.Block(body=[resolve_block_item(block) for block in body.body])


def check_labels_in_program(body: list[parser.Block_Item]):
    """
    Checks for:
    * using the same label for two labeled statements in the program function
    """
    found_labels: set[str] = set()
    requested_labels: set[str] = set()

    def match_stmt(stmt: parser.Block_Item):
        if not isinstance(stmt, parser.Statement):
            return
        match stmt.root:
            case parser.Break() | parser.Continue():
                pass
            case (
                parser.While(body=body)
                | parser.DoWhile(body=body)
                | parser.For(body=body)
                | parser.Switch(body=body)
                | parser.SwitchCase(body=body)
            ):
                match_stmt(body)
            case parser.Block(body=body):
                for b in body:
                    match_stmt(b)
            case parser.Goto(label=label):
                requested_labels.add(label.root)
            case parser.Label(label=label, statement=inner):
                if label.root in found_labels:
                    raise ValueError(f"Label {item} declared multiple times!")
                found_labels.add(label.root)
                match_stmt(inner)
            case parser.ReturnStatement() | parser.Expression() | "nope":
                pass
            case parser.IfStatement(then=then, else_s=else_s):
                match_stmt(then)
                if else_s:
                    match_stmt(else_s)

    for item in body:
        match_stmt(item)
    if requested_labels - found_labels != set():
        raise ValueError(
            f"Missing some requested labels!\n{found_labels=}\n{requested_labels=}"
        )


def resolve_block_item(block: parser.Block_Item):
    match block:
        case parser.Declaration():
            return resolve_declaration(block)
        case parser.Statement():
            return resolve_statement(block)


def resolve_for_init(for_init: parser.For_Init) -> parser.For_Init:
    match for_init:
        case None:
            return None
        case parser.Declaration():
            return resolve_declaration(for_init)
        case parser.Expression():
            return resolve_expression(for_init)


def resolve_declaration(decl: parser.Declaration):
    old_name = decl.name.root
    variable_map = VARIABLE_MAP.get()
    if not variable_map.valid_declaration(old_name):
        raise ValueError("Duplicate name!")

    new_name = variable_map.get_new_name(old_name)
    new_id = parser.Identifier(new_name)

    if decl.init is None:
        return parser.Declaration(type=decl.type, name=new_id, init=None)

    new_exp = resolve_expression(decl.init)

    return parser.Declaration(type=decl.type, name=new_id, init=new_exp)


def get_new_name(original: str, *, valid_c: bool = False):
    global Global_Counter
    # Note: We ensure that the new name is not valid-c
    # Otherwise the variables `int a, a1` could both be renamed to
    # `a12`
    new_name = (
        f"{original}_{Global_Counter}" if valid_c else f"{original}`{Global_Counter}"
    )

    Global_Counter += 1
    return new_name


def resolve_statement(stmt: parser.Statement) -> parser.Statement:
    match stmt.root:
        case "nope":
            return stmt

        case parser.Break():
            if not (control_label := get_control_label()):
                raise ValueError("No control label found!")
            return parser.Statement(root=parser.Break(control_label=control_label))
        case parser.Continue():
            if not (control_label := get_control_label("loop")):
                raise ValueError("No control label found!")
            return parser.Statement(root=parser.Continue(control_label=control_label))
        case parser.For(init=init, condition=condition, post=post, body=body):
            with (
                pf.set_context(VARIABLE_MAP, VARIABLE_MAP.get().get_copy()),
                pf.set_context(LOOP_CONTROL_LABEL, _get_new_name("for_label")),
                pf.set_context(MOST_RECENT_CONTROL_LABEL, LOOP_CONTROL_LABEL),
            ):
                init = resolve_for_init(init)
                condition = resolve_expression(condition) if condition else None
                post = resolve_expression(post) if post else None
                body = resolve_statement(body)
                return parser.Statement(
                    root=parser.For(
                        init=init,
                        condition=condition,
                        post=post,
                        body=body,
                        control_label=LOOP_CONTROL_LABEL.get(),
                    )
                )
        case (
            parser.DoWhile(condition=condition, body=body)
            | parser.While(condition=condition, body=body)
        ):
            with (
                pf.set_context(VARIABLE_MAP, VARIABLE_MAP.get().get_copy()),
                pf.set_context(LOOP_CONTROL_LABEL, _get_new_name("while_label")),
                pf.set_context(MOST_RECENT_CONTROL_LABEL, LOOP_CONTROL_LABEL),
            ):
                condition = resolve_expression(condition)
                body = resolve_statement(body)
                cls = stmt.root.__class__
                return parser.Statement(
                    root=cls(
                        body=body,
                        condition=condition,
                        control_label=LOOP_CONTROL_LABEL.get(),
                    )
                )
        case parser.Block():
            with pf.set_context(VARIABLE_MAP, VARIABLE_MAP.get().get_copy()):
                return parser.Statement(root=resolve_block(stmt.root))

        case parser.Expression():
            return parser.Statement(root=resolve_expression(stmt.root))

        case parser.ReturnStatement(exp=exp):
            return parser.Statement(
                root=parser.ReturnStatement(
                    exp=resolve_expression(exp),
                )
            )

        case parser.IfStatement(condition=condition, then=then, else_s=else_s):
            return parser.Statement(
                root=parser.IfStatement(
                    condition=resolve_expression(condition),
                    then=resolve_statement(then),
                    else_s=resolve_statement(else_s) if else_s else None,
                )
            )

        case parser.Goto(label=label):
            return parser.Statement(root=parser.Goto(label=resolve_goto_label(label)))

        case parser.Label(label=label, statement=statement):
            return parser.Statement(
                root=parser.Label(
                    label=resolve_goto_label(label),
                    statement=resolve_statement(statement),
                )
            )

        case parser.Switch(checker=checker, body=body):
            found_cases: dict[str, parser.SwitchCase] = {}
            switch_label = _get_new_name("switch_label")
            with (
                pf.set_context(SWITCH_CONTROL_LABEL, switch_label),
                pf.set_context(FOUND_CASES, found_cases),
                pf.set_context(MOST_RECENT_CONTROL_LABEL, SWITCH_CONTROL_LABEL),
            ):
                checker = resolve_expression(checker)
                body = resolve_statement(body)
            return parser.Statement(
                root=parser.Switch(
                    checker=checker,
                    body=body,
                    associated_cases=list(found_cases.values()),
                    control_label=switch_label,
                )
            )
        case parser.SwitchCase(type=type, body=body):
            if not (control_label := get_control_label("switch")):
                raise ValueError("No control label found!")
            body = resolve_statement(body)
            # We have to make sure that these cases were not used already in the same context
            found_cases = FOUND_CASES.get()
            as_str = type.model_dump_json()
            assert as_str not in found_cases, "This case was already found!"
            match type:
                case parser.SwitchCase.Case(check=check):
                    assert check.is_const_expression(), "Not a constant expression bro!"
                    type = parser.SwitchCase.Case(check=resolve_expression(check))
                case parser.SwitchCase.Default():
                    pass
            resolved = parser.SwitchCase(
                type=type,
                body=body,
                control_label=control_label,
                label=parser.Identifier(_get_new_name("case")),
            )
            found_cases[as_str] = resolved
            return parser.Statement(root=resolved)


def resolve_assignable(
    identifier: parser.Identifier | parser.Expression | parser.Factor,
):
    if isinstance(identifier, (parser.Expression, parser.Factor)):
        current = identifier
        # Solves situations like so:
        # `((((((2))))))`
        #
        # Note: This SHOULD have been taken care of before we hit this spot
        # But just in case...
        while hasattr(current, "type") and not isinstance(current.type, str):  # pyright: ignore[reportAttributeAccessIssue, reportUnknownArgumentType, reportUnknownMemberType]
            current = current.type  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(current, parser.Unary):
            # Postfix and pre-fix operators being a PITA as usual
            # This is a valid assignable value `~a++`
            assert current.type not in ("++", "--")
            return parser.Expression(
                type=parser.Factor(
                    type=parser.Unary(
                        type=current.type,
                        exp=resolve_assignable(current.exp).type,  # pyright: ignore[reportArgumentType, reportUnknownArgumentType, reportUnknownMemberType]
                        pre=current.pre,
                    )
                )
            )
        assert isinstance(current, parser.Identifier), f"{current} is not assignable!"
        identifier = current

    return parser.Expression(
        type=parser.Factor(type=resolve_identifier(identifier, VARIABLE_MAP.get()))
    )


def resolve_goto_label(label: parser.Identifier):
    return resolve_identifier(
        label,
        where_to_check=LABEL_MAP.get(),
        ok_to_not_be_declared=True,
        valid_c=False,
    )


def resolve_identifier(
    identifier: parser.Identifier,
    where_to_check: Label_Map | Variable_Map,
    *,
    ok_to_not_be_declared: bool = False,
    valid_c: bool = False,
):
    """
    In some cases - it's ok for our name to not be declared
    """
    name = identifier.root

    resolved_name = where_to_check[name]

    if resolved_name is None:
        if ok_to_not_be_declared:
            resolved_name = where_to_check.get_new_name(name, valid_c=valid_c)
        else:
            raise ValueError(f"Identifier {name} not found!")

    return parser.Identifier(root=resolved_name)


def resolve_factor(factor: parser.Factor) -> parser.Factor:
    match factor.type:
        case parser.Constant():
            return factor
        case parser.Expression():
            return parser.Factor(type=resolve_expression(factor.type))
        case parser.Identifier():
            return parser.Factor(type=resolve_assignable(factor.type))
        case parser.Unary(type=type, exp=exp, pre=pre):
            if type not in ("++", "--"):
                return parser.Factor(
                    type=parser.Unary(type=type, exp=resolve_factor(exp), pre=pre)
                )
            # assert the boy is an lvalue
            return parser.Factor(
                type=parser.Unary(
                    type=type,
                    exp=resolve_assignable(exp).type,  # pyright: ignore[reportArgumentType]
                    pre=pre,
                )
            )


def resolve_expression(exp: parser.Expression) -> parser.Expression:
    match exp.type:
        case parser.Conditional(left=left, middle=middle, right=right):
            return parser.Expression(
                type=parser.Conditional(
                    left=resolve_expression(left),
                    middle=resolve_expression(middle),
                    right=resolve_expression(right),
                )
            )
        case parser.NormalAssigment(lhs=lhs, rhs=rhs):
            return parser.Expression(
                type=parser.NormalAssigment(
                    lhs=resolve_assignable(lhs),
                    rhs=resolve_expression(rhs),
                )
            )
        case parser.FancyAssignment(lhs=lhs, rhs=rhs, type=type):
            # Pyright needed some help here
            rhs: parser.Expression

            def get_bin_op(type: parser.Binary_Op_Without_Assignment):
                return parser.Expression(
                    type=parser.BinaryOp(
                        type=type,
                        lhs=parser.Expression(type=parser.Factor(type=lhs)),
                        rhs=rhs,
                    )
                )

            match type:
                case "+=":
                    rhs = get_bin_op("PLUS")
                case "-=":
                    rhs = get_bin_op("MINUS")
                case "*=":
                    rhs = get_bin_op("ASTERISK")
                case "%=":
                    rhs = get_bin_op("PERCENT")
                case "&=":
                    rhs = get_bin_op("AMPERSAND")
                case "|=":
                    rhs = get_bin_op("PIPE")
                case "^=":
                    rhs = get_bin_op("CARRET")
                case "<<=":
                    rhs = get_bin_op("LEFT_SHIFT")
                case ">>=":
                    rhs = get_bin_op("RIGHT_SHIFT")
                case "/=":
                    rhs = get_bin_op("FORWARD_SLASH")

            return parser.Expression(
                type=parser.NormalAssigment(
                    lhs=resolve_assignable(lhs),
                    rhs=resolve_expression(rhs),
                )
            )

        case parser.Factor():
            return parser.Expression(type=resolve_factor(exp.type))

        case parser.BinaryOp(lhs=lhs, rhs=rhs, type=type):
            return parser.Expression(
                type=parser.BinaryOp(
                    type=type,
                    lhs=resolve_expression(lhs),
                    rhs=resolve_expression(rhs),
                )
            )


def _get_new_name(original: str, *, valid_c: bool = False):
    global Global_Counter
    # Note: We ensure that the new name is not valid-c
    # Otherwise the variables `int a, a1` could both be renamed to
    # `a12`
    new_name = (
        f"{original}_{Global_Counter}" if valid_c else f"{original}`{Global_Counter}"
    )
    Global_Counter += 1
    return new_name
