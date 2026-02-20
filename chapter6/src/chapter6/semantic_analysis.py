import chapter6.parser as parser

VARIABLE_MAP: dict[str, str] = {}
"""
TODO(Joaquim): Use contextvar
Various functions will no doubt declare their own little `i` variables
"""

Global_Counter: int = -1
"""
Will be used during tacky as well.
This is to ensure that the tacky-boys don't somehow end up using the same
name as this one.
"""


def resolve_program(prog: parser.Program):
    func = prog.function
    new_blocks = [resolve_block_item(block) for block in func.body]

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


def resolve_block_item(block: parser.Block_Item):
    match block:
        case parser.Declaration():
            return resolve_declaration(block)
        case parser.Statement():
            return resolve_statement(block)


def resolve_declaration(decl: parser.Declaration):
    global Global_Counter

    old_name = decl.name
    if old_name.root in VARIABLE_MAP:
        raise ValueError("Duplicate name!")

    # Note: We ensure that the new name is not valid-c
    # Otherwise the variables `int a, a1` could both be renamed to
    # `a12`
    new_name = f"{decl.name.root}`{Global_Counter}"

    Global_Counter += 1
    VARIABLE_MAP[decl.name.root] = new_name

    new_id = parser.Identifier(new_name)

    if decl.init is None:
        return parser.Declaration(type=decl.type, name=new_id, init=None)

    new_exp = resolve_expression(decl.init)

    return parser.Declaration(type=decl.type, name=new_id, init=new_exp)


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


def resolve_identifier(identifier: parser.Identifier | parser.Expression):
    match identifier:
        case (
            parser.Identifier(root=name)
            | parser.Expression(type=parser.Factor(type=parser.Identifier(root=name)))
        ):
            pass
        case _:
            raise ValueError("For now, only identifiers can go here!")

    assert name in VARIABLE_MAP, "Unknown variable!"

    return parser.Expression(
        type=parser.Factor(
            type=parser.Identifier(
                root=VARIABLE_MAP[name],
            )
        )
    )


def resolve_factor(factor: parser.Factor) -> parser.Factor:
    match factor.type:
        case parser.Constant():
            return factor
        case parser.Expression():
            return parser.Factor(type=resolve_expression(factor.type))
        case parser.Identifier():
            return parser.Factor(type=resolve_identifier(factor.type))
        case parser.Unary(type=type, exp=exp, pre=pre):
            return parser.Factor(
                type=parser.Unary(type=type, exp=resolve_factor(exp), pre=pre)
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
                    lhs=resolve_identifier(lhs),
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
                    lhs=resolve_identifier(lhs),
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
