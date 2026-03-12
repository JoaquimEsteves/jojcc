import typing as t

from collections import abc
import chapter6.parser as parser

VARIABLE_MAP: dict[str, str] = {}
"""
TODO(Joaquim): Use contextvar
Various functions will no doubt declare their own little `i` variables
"""
LABEL_MAP: dict[str, str] = {}

Global_Counter: int = 0
"""
Will be used during tacky as well.
This is to ensure that the tacky-boys don't somehow end up using the same
name as this one.
"""


def resolve_program(prog: parser.Program):
    func = prog.function
    new_blocks = check_labels_in_function(
        [resolve_block_item(block) for block in func.body]
    )

    if func.return_type.root == "int":
        # Ensures that there's always a return statement at the end
        new_blocks.append(
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


def check_labels_in_function(body: list[parser.Block_Item]) -> list[parser.Block_Item]:
    """
    Checks for:
    * using the same label for two labeled statements in the same function
    """
    found_labels: set[str] = set()
    requested_labels: set[str] = set()

    def match_stmt(stmt: parser.Statement):
        match stmt.root:
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

    for item in t.cast(
        abc.Iterable[parser.Statement],
        filter(lambda b: isinstance(b, parser.Statement), body),
    ):
        match_stmt(item)
    if requested_labels - found_labels != set():
        raise ValueError(
            f"Missing some requested labels!\n{found_labels=}\n{requested_labels=}"
        )
    return body


def resolve_block_item(block: parser.Block_Item):
    match block:
        case parser.Declaration():
            return resolve_declaration(block)
        case parser.Statement():
            return resolve_statement(block)


def resolve_declaration(decl: parser.Declaration):
    old_name = decl.name.root
    if old_name in VARIABLE_MAP:
        raise ValueError("Duplicate name!")

    new_name = get_new_name(old_name)
    VARIABLE_MAP[old_name] = new_name
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
        while hasattr(current, "type"):  # pyright: ignore[reportUnknownArgumentType]
            current = current.type  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        assert isinstance(current, parser.Identifier), f"{current} is not assignable!"
        identifier = current

    return parser.Expression(type=parser.Factor(type=resolve_identifier(identifier)))


def resolve_goto_label(label: parser.Identifier):
    return resolve_identifier(
        label, where_to_check=LABEL_MAP, ok_to_not_be_declared=True, valid_c=False
    )


def resolve_identifier(
    identifier: parser.Identifier,
    where_to_check: dict[str, str] = VARIABLE_MAP,
    *,
    ok_to_not_be_declared: bool = False,
    valid_c: bool = False,
):
    """
    In some cases - it's ok for our name to not be declared
    """
    name = identifier.root

    if name not in where_to_check:
        if ok_to_not_be_declared:
            where_to_check[name] = get_new_name(name, valid_c=valid_c)
        else:
            raise ValueError(f"Identifier {name} not found!")

    return parser.Identifier(root=where_to_check[name])


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
