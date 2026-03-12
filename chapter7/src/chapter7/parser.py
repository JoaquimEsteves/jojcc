"""
AST Definition

New shit in underscore

```
<program> ::= <function>
<function> ::= "int" <identifier> "(" "void" ")" "{" {<block-item>} "}"
_<block> ::= "{" {<block-item} "}"_
<block-item> ::= <statement> | <declaration>
<declaration> ::= "int" <identifier> ["=" <exp>] ";"
<statement> ::= "return" <exp> ";"
    | <exp> ";"
    | ";"
    | "if" "(" <exp> ")" <statement> ["else" <statement>]
    | goto <identifier>;
    | <identifier>: <statement>
    | _<block>_
<exp> ::= <factor> | <exp> <binop> <exp> | <exp> "?" <exp> ":" <exp>
<factor> ::= <int> | <identifier> | <unop> <factor> | <factor> <postop> | "(" <exp> ")" |
<unop> ::= "-" | "~" | "!" | "++" | "--"
<postop> ::= "++" | "--"
<binop> ::= "-" | "+" | "*" | "/" | "%" | "&&" | "||"
          | "==" | "!=" | "<" | "<=" | ">" | ">=" | "="
          | "+=" | "-=" | "*=" | "%=" | "&=" | "|=" | "^=" | "<<=" | ">>="
<identifier> ::= ? An identifier token ?
<int> ::= ? A constant token ?
```

Notes:

> While parsing <block-item>, you need a way to tell whether the current block
> item is a statement or a declaration. To do this, peek at the first token; if
> it's the int keyword, it's a declaration, and otherwise it's a statement.

"""

import typing as t
from contextlib import suppress
from textwrap import dedent

import shared.data_types as dt
import shared.pure_functions as pf
from pydantic import BaseModel, RootModel, model_validator

from chapter7 import lexer


class Program(BaseModel):
    """
    <program> ::= <function>
    """

    function: Function

    @staticmethod
    def from_tokens(tokens: lexer.Lexed):
        return Program(function=Function.from_tokens(tokens))

    @t.override
    def __str__(self):
        return str(self.function)


class Function(BaseModel):
    """
    <function> ::= "int"<identifier>"(""void"")""{"<statement>"}
    """

    return_type: CType
    name: Identifier
    body: Block

    @t.override
    def __str__(self):
        start = pf.indent(
            dedent(
                f"""
                    (function
                      ('name {self.name.root})
                      ('return_type {self.return_type.root})
                      ('body
                      """
            )
        )
        with pf.set_context(dt.INDENT_LEVEL, dt.INDENT_LEVEL.get() + 1):
            str_body = str(self.body)
        with pf.set_context(dt.INDENT_LEVEL, dt.INDENT_LEVEL.get() + 2):
            body = pf.indent(str_body)
        return f"{start}{body})"

    @staticmethod
    def from_tokens(tokens: lexer.Lexed):
        try:
            (
                type,
                identifier,
                (_, parens, _),
                (_, void, _),
                (_, closeparens, _),
                (bracket, _, _),
                *rest,
            ) = tokens

        except ValueError as e:
            raise ValueError(
                f"Nope, function must look like: {Function.__doc__}"
            ) from e

        assert parens == "(", (  # )
            "Where's the ( brother?"  # )
        )  # <- keep these here for vims indent
        assert void == "void", "Where's the void brother?"
        assert closeparens == ")", "Where's the ) brother?"
        assert closeparens == ")", "Where's the ) brother?"
        assert bracket == "{", (
            "Where's the { brother?"
        )  # } }  <- keep these here for vims indent

        closing_bracket_index = get_closing(rest, "}")

        assert not rest[closing_bracket_index + 1 :], (
            "How the heck is there more stuff after the last bracket?"
        )

        body = rest[0:closing_bracket_index]

        assert rest[closing_bracket_index + 1 :] == [], (
            "For now we only accept one function per program yo"
        )

        return Function(
            return_type=CType.from_tokens(type),
            name=Identifier.from_tokens(identifier),
            body=Block.from_tokens(body),
        )


type Block_Item = Statement | Declaration


class Declaration(BaseModel):
    """
    <declaration> ::= "int" <identifier> ["=" <exp>] ";"_
    """

    type: CType
    name: Identifier
    init: Expression | None

    @t.override
    def __str__(self):
        pre = f"(let {self.name!s}:{self.type.root}"
        if not self.init:
            return pre + ")"
        return f"{pre} '{self.init or 'void'})"

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> tuple[Declaration, lexer.Lexed] | None:
        if len(tokens) < 2:
            return None
        type, identifier, *rest = tokens

        ctype: CType | None = None
        name: Identifier | None = None

        with suppress(AssertionError):
            ctype = CType.from_tokens(type)
        with suppress(AssertionError):
            name = Identifier.from_tokens(identifier)

        if ctype is None or name is None:
            return None

        (next_token, *_), *rest = rest
        match next_token:
            case "=":
                exp, rest = Expression.from_tokens(rest)

                (next, *_), *rest = rest

                assert next == "SEMICOLON", "Missing semicolon!"

                return Declaration(type=ctype, name=name, init=exp), rest
            case "SEMICOLON":
                return Declaration(type=ctype, name=name, init=None), rest
            case _:
                raise ValueError("Syntax error!")


class CType(RootModel[str]):
    # TODO(Joaquim): Get rid of this awfulness

    @staticmethod
    def from_tokens(token: lexer.Token_Lexed):
        assert token[0] == "INT_KEYWORD", "I know of no other CTypes! Sorry"
        assert token[1] == "int"
        return CType(token[1])


class ReturnStatement(BaseModel):
    exp: Expression

    @t.override
    def __str__(self):
        return f"(return {self.exp!s})"


class IfStatement(BaseModel):
    condition: Expression
    then: Statement
    else_s: Statement | None = None

    @t.override
    def __str__(self):
        res = f"(if {self.condition!s}\n"
        body = [str(self.then)]
        if self.else_s:
            body.append(str(self.else_s))
        body = pf.indent("\n".join(body))
        return f"{res}{body})"


class Statement(BaseModel):
    """
    <statement> ::= "return" <exp> ";"
        | <exp> ";"
        | ";"
        | _"if" "(" <exp> ")" <statement> ["else" <statement>]_
        | goto <identifier>;
        | <identifier>:
        | <block>
    """

    root: (
        ReturnStatement
        | Expression
        | t.Literal["nope"]
        | IfStatement
        | Goto
        | Label
        | Block
    )

    @t.override
    def __str__(self):
        return str(self.root)

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> tuple[Statement, lexer.Lexed] | None:
        (next_token, *_), *rest = tokens

        def get_back_expression():
            # Well then it must be an expression followed by a semicolon
            exp, rest = Expression.from_tokens(tokens)

            (semicolon, *_), *rest = rest
            assert semicolon == "SEMICOLON", "Missing semicolon!"
            return Statement(root=exp), rest

        match next_token:
            case "SEMICOLON":
                return Statement(root="nope"), rest
            case "RETURN_KEYWORD":
                exp, rest = Expression.from_tokens(rest)

                (semicolon, *_), *rest = rest
                assert semicolon == "SEMICOLON", "Missing semicolon!"
                return Statement(root=ReturnStatement(exp=exp)), rest
            case "IF_KEYWORD":
                (open_parens, *_), *rest = rest
                assert open_parens == "OPEN_PARENS", "I need some parens bro"
                closed_parens = get_closing(rest, ")")
                expression = Expression.from_tokens(
                    rest[:closed_parens], assert_no_food_left=True
                )

                statement = Statement.from_tokens(rest[closed_parens + 1 :])
                assert statement, "An if needs a statement brother!"
                then_stmt, rest = statement
                else_stmt = None

                next_token = ""
                if rest:
                    (next_token, *_), *maybe = rest
                if next_token == "ELSE_KEYWORD":
                    # Alrighty
                    statement = Statement.from_tokens(maybe)  # pyright: ignore[reportPossiblyUnboundVariable]
                    assert statement, "We need a statement after the else brother!"
                    else_stmt, rest = statement
                return Statement(
                    root=IfStatement(
                        condition=expression, then=then_stmt, else_s=else_stmt
                    )
                ), rest

            case "GOTO":
                identifier, (semicolon, *_), *rest = rest
                assert identifier[0] == "IDENTIFIER", (
                    "After a `goto` we need an identifier!"
                )
                assert semicolon == "SEMICOLON", "Where the semicolon at?!"

                return Statement(
                    root=Goto(label=Identifier.from_tokens(identifier))
                ), rest
            case "IDENTIFIER":
                (colon, *_), *maybe = rest
                # Labeled statement
                if colon == ":":
                    child = Statement.from_tokens(maybe)
                    assert child is not None, "Nope! A label requires a statement"
                    child_stmt, rest = child
                    return Statement(
                        root=Label(
                            label=Identifier.from_tokens(tokens[0]),
                            statement=child_stmt,
                        )
                    ), rest
                # probably an expression
                return get_back_expression()

            case "{":
                closing_bracket_index = get_closing(rest, "}")
                return Statement(
                    root=Block.from_tokens(
                        rest[0:closing_bracket_index],
                    )
                ), rest[closing_bracket_index + 1 :]

            case _:
                # probably an expression
                return get_back_expression()


class Goto(BaseModel):
    label: Identifier

    @t.override
    def __str__(self):
        return f"(goto {self.label!s})"


class Label(BaseModel):
    label: Identifier
    statement: Statement

    @t.override
    def __str__(self):
        return f"(label {self.label!s}\n{pf.indent(str(self.statement))})"


class Block(BaseModel):
    body: list[Block_Item]

    @t.override
    def __str__(self):
        start = "(scope\n"
        return f"{start}{pf.indent('\n'.join(str(b) for b in self.body))})"

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> Block:
        parsed_body: list[Block_Item] = []

        while tokens:
            block_item = Declaration.from_tokens(tokens) or Statement.from_tokens(
                tokens
            )
            if block_item is None:
                raise ValueError("I accept declarations or statements!")
            item, tokens = block_item

            parsed_body.append(item)

        return Block(body=parsed_body)


class Expression(BaseModel):
    """
    <exp> ::= <factor> | <exp> <binop> <exp> | <exp> "?" <exp> ":" <exp>
    """

    type: BinaryOp | Factor | FancyAssignment | NormalAssigment | Conditional

    @model_validator(mode="after")
    def fix_paren_jank(self):
        """
        Fixes situations like:

        ```c
        int a = ((((((((2))))))));
        ```
        """
        match self.type:
            case Factor(type=Expression(type=inner)):
                self.type = inner
            case _:
                pass
        return self

    @staticmethod
    def read_var(name: str):
        return Expression(type=Factor(type=Identifier(name)))

    @t.override
    def __str__(self):
        return str(self.type)

    @t.overload
    @staticmethod
    def from_tokens(
        tokens: lexer.Lexed,
        *,
        assert_no_food_left: t.Literal[False] = False,
        min_prec: int = 0,
    ) -> tuple[Expression, lexer.Lexed]: ...

    @t.overload
    @staticmethod
    def from_tokens(
        tokens: lexer.Lexed, *, assert_no_food_left: t.Literal[True], min_prec: int = 0
    ) -> Expression:
        """
        If we specify `assert_no_food_left` then we assert that the tokens we _would_ return are empty.
        """

    @staticmethod
    def from_tokens(
        tokens: lexer.Lexed, *, assert_no_food_left: bool = False, min_prec: int = 0
    ) -> tuple[Expression, lexer.Lexed] | Expression:
        def inner(
            tokens: lexer.Lexed, min_prec: int = 0
        ) -> tuple[Expression, lexer.Lexed]:
            left, right = Factor.parse(tokens)
            while right:
                (operator, _identifier, _), *rest = right

                if operator not in BINARY_OP_PRECEDENCE:
                    break

                if BINARY_OP_PRECEDENCE[operator] < min_prec:
                    # Let the other nerds handle this!
                    break

                if operator in ("++", "--"):
                    # shit, I hate these nerds
                    other_rest = rest
                    left = Factor(
                        type=Unary(
                            type=operator,
                            exp=left,  # pyright: ignore[reportArgumentType]
                            pre=False,
                        ),
                    )

                # RIGHT ASSOCIATIVITY VS LEFT ASSOCIATIVITY
                # See chapter5/README.md
                elif operator in lexer.ASSIGNMENT_OPS:
                    # special case!
                    rhs, other_rest = inner(rest, BINARY_OP_PRECEDENCE[operator])

                    identifier = Expression(type=left)
                    left = (
                        FancyAssignment(lhs=identifier, rhs=rhs, type=operator)
                        if operator != "="
                        else NormalAssigment(lhs=identifier, rhs=rhs)
                    )
                elif operator == "?":
                    middle, rhs = inner(rest, 0)
                    (colon, *_), *rhs = rhs
                    assert colon == ":", "BAD IF EXPRESSION"
                    right, other_rest = inner(rhs, BINARY_OP_PRECEDENCE[operator])
                    left = Conditional(
                        left=Expression(type=left), middle=middle, right=right
                    )

                else:
                    # Don't quite understand this +1 if I must be honest
                    rhs, other_rest = inner(rest, BINARY_OP_PRECEDENCE[operator] + 1)
                    left = BinaryOp(
                        type=operator,  # pyright: ignore[reportArgumentType]
                        lhs=Expression(type=left),
                        rhs=rhs,
                    )
                right = other_rest

            return Expression(type=left), right

        exp, rest = inner(tokens, min_prec)
        if assert_no_food_left:
            assert rest == [], "We left food on the table!"
            return exp
        return exp, rest


class Constant(RootModel[int]):
    @t.override
    def __str__(self):
        return str(self.root)


class Factor(BaseModel):
    """
    The name `factor` comes from the fact that this symbol can appear as a
    _factor_ in a multiplication expression.

    """

    type: Constant | Unary | Expression | Identifier

    @t.override
    def __str__(self):
        match self.type:
            case Constant(root=root):
                return str(root)
            case Unary():
                return str(self.type)
            case Expression() | Identifier():
                return str(self.type)

    @staticmethod
    def parse(tokens: lexer.Lexed) -> tuple[Factor, lexer.Lexed]:
        (token, identifier, lineno), *rest = tokens
        match token:
            case "IDENTIFIER":
                ident = Identifier.from_tokens((token, identifier, lineno))
                exp = Factor(
                    type=Identifier.from_tokens((token, identifier, lineno)),
                )
                return Factor(
                    type=ident,
                ), rest
            case "CONSTANT":
                return Factor(
                    type=Constant(identifier),  # pyright: ignore[reportArgumentType]
                ), rest
            case "OPEN_PARENS":
                corresponding_closed = get_closing(rest, ")")
                return Factor(
                    type=Expression.from_tokens(
                        rest[:corresponding_closed], assert_no_food_left=True
                    )
                ), rest[corresponding_closed + 1 :]

            case "COMPLEMENT" | "MINUS" | "NOT" | "++" | "--":
                exp, rest = Factor.parse(rest)
                return Factor(
                    type=Unary(type=token, exp=exp),
                ), rest
            case _:
                raise AssertionError(f"Syntax Error, unknown {token=} at {lineno=}")


class Unary(BaseModel):
    type: t.Literal[
        "COMPLEMENT",
        "MINUS",
        "NOT",
        "--",
        "++",
    ]
    exp: Factor
    pre: bool = True

    @t.override
    def __str__(self):
        return f"({self.type!s} {self.exp!s} {'' if self.pre else 'postfix'})"


type Simple_Binary = t.Literal[
    "MINUS",
    "PLUS",
    "ASTERISK",
    "AMPERSAND",
    "PIPE",
    "CARRET",
    "LEFT_SHIFT",
    "RIGHT_SHIFT",
]

type Relational_Binary = t.Literal[
    "LE",
    "LT",
    "GT",
    "GE",
    "==",
    "!=",
]

type Jumpy_Binary_Op = t.Literal["AND", "OR"]
"""
These nerds are special, since they'll do a little jump
and not execute the right-side (sometimes)
"""


type Binary_Op_Without_Assignment = (
    Simple_Binary
    | Relational_Binary
    | t.Literal[
        "FORWARD_SLASH",
        "PERCENT",
    ]
    | Jumpy_Binary_Op
)

type Binary_Operation = Binary_Op_Without_Assignment | lexer.Assignment_Ops

type Binary_Op_Or_Extras = Binary_Operation | t.Literal["?", "++", "--"]
"""
According to _the book_ we can just re-use the code for binary-expressions here
and treat `cond ? foo : bar` as a binary operator except that the operator is
actually `? foo :`
"""


def _binary_op_precedence(op: Binary_Op_Or_Extras):
    """
    The reference is:
    https://en.cppreference.com/w/c/language/operator_precedence.html

    The code expects that higher -> more priority (reverse of the above reference)
    So we just subtract some large number and we're off to the races

    Note: We use a `match` just so that we don't forget any literal.
    Type-checkers will then have our back.

    """
    match op:
        case "++" | "--":
            return 100 - 1
        case "ASTERISK" | "FORWARD_SLASH" | "PERCENT":
            return 100 - 3
        case "MINUS" | "PLUS":
            return 100 - 4
        case "LEFT_SHIFT" | "RIGHT_SHIFT":
            return 100 - 5
        case "LE" | "LT" | "GE" | "GT":
            return 100 - 6
        case "==" | "!=":
            return 100 - 7
        case "AMPERSAND":
            return 100 - 8
        case "CARRET":
            return 100 - 9
        case "PIPE":
            return 100 - 10
        case "AND":
            return 100 - 11
        case "OR":
            return 100 - 12
        case "?":
            return 100 - 13
        case (
            "=" | "+=" | "-=" | "*=" | "%=" | "&=" | "|=" | "^=" | "<<=" | ">>=" | "/="
        ):
            return 100 - 14


BINARY_OP_PRECEDENCE: dict[Binary_Op_Or_Extras, int] = {
    op: _binary_op_precedence(op)
    for op in t.cast(
        frozenset[Binary_Op_Or_Extras], pf.get_literal_vals(Binary_Op_Or_Extras)
    )
}


class BinaryOp(BaseModel):
    type: Binary_Op_Without_Assignment
    lhs: Expression
    rhs: Expression

    @t.override
    def __str__(self):
        return f"({self.type} {self.lhs.type!s} {self.rhs.type!s})"


class NormalAssigment(BaseModel):
    lhs: LValue
    rhs: Expression

    @t.override
    def __str__(self):
        return f"(= {self.lhs!s} {self.rhs.type!s})"


class Conditional(BaseModel):
    left: Expression
    middle: Expression
    right: Expression

    @t.override
    def __str__(self):
        res = f"(if-expr {self.left!s}\n"
        body = pf.indent("\n".join(map(str, [self.middle, self.right])))
        return f"{res}{body})"


LValue = t.Annotated["Expression | Identifier", "FIX ME LATER"]
"""
This is wrong - not everything can be an lvalue But for some reason _THE BOOK_
wants me to "just accept" expressions here and to see if they're a valid LValue
later.

In future chapters we'll look more in depth at what an `LVALUE` is, I (hope) that I can then
just add some sort of annotation to clean up my classes, 'cos this whole `LValue` is any type #YOLO
feels rough

Note: Making this _not_ a type is important or pydantic cries about a circular  reference schema
"""


class FancyAssignment(BaseModel):
    type: lexer.Fancy_Assignment_Ops
    lhs: LValue
    rhs: Expression

    @t.override
    def __str__(self):
        return f"({self.type} {self.lhs!s} {self.rhs.type!s})"


class Identifier(RootModel[str]):
    @staticmethod
    def from_tokens(token: lexer.Token_Lexed):
        ltoken, identifier, _ = token
        assert ltoken == "IDENTIFIER", "Not an identifier!"
        # TODO(Joaquim): Add asserts for forbidden identifiers
        # Stoping stuff like `True = False`
        # Use pydantic
        return Identifier(identifier)

    @t.override
    def __str__(self):
        return f"`{self.root}`"


def get_closing(tokens: lexer.Lexed, closing_symbol: t.Literal["}", ")"]) -> int:
    open_symbol = "{" if closing_symbol == "}" else "("
    number_of_open = 1
    number_of_closed = 0
    for index, (_, lexed, _) in enumerate(tokens):
        if lexed == closing_symbol:
            number_of_closed += 1
            if number_of_closed == number_of_open:
                return index
        if lexed == open_symbol:
            number_of_open += 1

    raise ValueError(f"Where's the '{closing_symbol}' brother?")
