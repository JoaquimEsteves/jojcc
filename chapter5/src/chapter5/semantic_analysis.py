import chapter5.parser as parser

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


def resolve_identifier(identifier: parser.Identifier):
    name = identifier.root
    assert name in VARIABLE_MAP, "Unknown variable!"
    new_name = VARIABLE_MAP[name]
    return parser.Identifier(new_name)


def resolve_factor(factor: parser.Factor) -> parser.Factor:
    match factor.type:
        case parser.Constant():
            return factor
        case parser.Expression():
            return parser.Factor(type=resolve_expression(factor.type))
        case parser.Identifier():
            return parser.Factor(type=resolve_identifier(factor.type))
        case parser.Unary(type=type, exp=exp):
            return parser.Factor(type=parser.Unary(type=type, exp=resolve_factor(exp)))


def resolve_expression(exp: parser.Expression) -> parser.Expression:
    match exp.type:
        case parser.Assignment(lhs=lhs, rhs=rhs):
            return parser.Expression(
                type=parser.Assignment(
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
