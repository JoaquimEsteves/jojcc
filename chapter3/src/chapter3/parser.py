"""
AST Definition

As ASDL (Zephyr Abstract Syntax Description Language)

```
<program> ::= <function>
<function> ::= "int" <identifier> "(" "void" ")" "{" <statement> "}"
<statement> ::= "return" <exp> ";"
<exp> ::= <factor> | <exp> <binop> <exp>
<factor> ::= <int> | <unop> <factor> | "(" <exp> ")"
<unop> ::= "-" | "~"
<binop> ::= "-" | "+" | "*" | "/" | "%"
<identifier> ::= ? An identifier token ?
<int> ::= ? A constant token ?
```
"""

from textwrap import dedent
import typing as t
from chapter3 import lexer

from pydantic import BaseModel, RootModel


class Program(BaseModel):
    """
    <program> ::= <function>
    """

    function: "Function"

    def __init__(self, tokens: lexer.Lexed):
        return super().__init__(function=Function(tokens))


class Function(BaseModel):
    """
    <function> ::= "int"<identifier>"(""void"")""{"<statement>"}
    """

    return_type: CType
    name: Identifier
    body: Statement

    @t.override
    def __repr__(self):
        return dedent(f"""
            (function
                ('name {self.name.root})
                ('return_type {self.return_type.root})
                ('body {repr(self.body.root.exp)})
        """)

    @staticmethod
    def get_closing_bracket_index(tokens: lexer.Lexed):
        for index, (_, lexed, _) in enumerate(tokens):
            if lexed == "}":
                return index

        raise ValueError("Where's the '}' brother?")

    def __init__(self, tokens: lexer.Lexed):
        try:
            (
                type,
                identifier,
                (_, parens, _),
                (_, void, _),
                (_, closeparens, _),
                (_, bracket, _),
                *rest,
            ) = tokens

        except ValueError as e:
            raise ValueError(f"Nope, function must look like: {self.__doc__}") from e

        assert parens == "(", "Where's the ( brother?"
        assert void == "void", "Where's the void brother?"
        assert closeparens == ")", "Where's the ) brother?"
        assert closeparens == ")", "Where's the ) brother?"
        assert bracket == "{", "Where's the { brother?"

        closing_bracket_index = self.get_closing_bracket_index(rest)
        assert not rest[closing_bracket_index + 1 :], "I'm just a baby parser bro!"

        body = rest[0:closing_bracket_index]

        return super().__init__(
            return_type=CType(type),
            name=Identifier(identifier),
            body=Statement(body),
        )


class CType(RootModel[str]):
    def __init__(self, token: lexer.Token_Lexed):
        assert token[0] == "INT_KEYWORD", "I know of no other CTypes! Sorry"
        assert token[1] == "int"
        return super().__init__(root=token[1])  # pyright: ignore[reportUnknownMemberType]


class ReturnStatement(BaseModel):
    exp: Expression

    def __init__(self, tokens: lexer.Lexed):
        (return_token, _, _) = tokens[0]
        (semicolon, _, _) = tokens[-1]
        assert return_token == "RETURN_KEYWORD", "Where's the 'return' brother?"
        assert semicolon == "SEMICOLON", "Where's the ';' brother?"

        return super().__init__(exp=Expression.parse(tokens[1:-1]))


class IfStatement(BaseModel):
    condition: Expression
    else_s: "Statement | None" = None

    def __init__(self, tokens: lexer.Lexed):
        super().__init__(condition="xD")
        raise NotImplementedError


class Statement(RootModel[ReturnStatement]):
    def __init__(self, tokens: lexer.Lexed):
        return super().__init__(root=ReturnStatement(tokens))  # pyright: ignore[reportUnknownMemberType]

    @t.override
    def __repr__(self):
        return repr(self.root)


class Expression(BaseModel):
    type: BinaryOp | Factor

    @t.override
    def __repr__(self):
        return repr(self.type)

    @staticmethod
    def parse(tokens: lexer.Lexed, min_prec: int = 0) -> Expression:
        def inner(
            tokens: lexer.Lexed, min_prec: int = 0
        ) -> tuple[Expression, lexer.Lexed]:
            left, right = Factor.parse(tokens)
            while right:
                (operator, _identifier, _), *rest = right

                if operator not in BINARY_OP_PRECEDENCE.keys():
                    break
                operator = t.cast(Binary_Operation, operator)
                if BINARY_OP_PRECEDENCE[operator] < min_prec:
                    # Let the other nerds handle this!
                    break

                # Don't quite understand this +1 if I must be honest
                rhs, other_rest = inner(rest, BINARY_OP_PRECEDENCE[operator] + 1)
                left = BinaryOp(type=operator, lhs=Expression(type=left), rhs=rhs)
                right = other_rest

            return Expression(type=left), right

        exp, rest = inner(tokens, min_prec)
        assert rest == [], "We left food on the table!"
        return exp


class Constant(RootModel[int]):
    pass


class Factor(BaseModel):
    """
    The name `factor` comes from the fact that this symbol can appear as a
    _factor_ in a multiplication expression.

    """

    type: Constant | Unary | Expression

    @t.override
    def __repr__(self):
        match self.type:
            case Constant():
                return repr(self.type.root)
            case Unary():
                return f"({self.type.type} {repr(self.type.exp)})"
            case Expression():
                return repr(self.type.type)

    @staticmethod
    def parse(tokens: lexer.Lexed) -> tuple[Factor, lexer.Lexed]:
        (token, identifier, lineno), *rest = tokens
        match token:
            case "CONSTANT":
                return Factor(
                    type=Constant(identifier),  # pyright: ignore[reportArgumentType]
                ), rest
            case "OPEN_PARENS":
                # BUG! Doesn't work with silly reduntant_parens!
                number_of_open = 1
                number_of_closed = 0
                corresponding_closed = None
                for index, token in enumerate(tokens[1:], start=1):
                    if token[0] == "OPEN_PARENS":
                        number_of_open += 1
                        continue
                    if token[0] == "CLOSE_PARENS":
                        number_of_closed += 1
                        if number_of_closed == number_of_open:
                            corresponding_closed = index
                            break

                assert corresponding_closed is not None, "You missed a parens bro!"
                return Factor(
                    type=Expression.parse(tokens[1:corresponding_closed])
                ), tokens[corresponding_closed + 1 :]

            case "COMPLEMENT" | "MINUS":
                exp, rest = Factor.parse(rest)
                return Factor(
                    type=Unary(type=token, exp=exp),
                ), rest
            case _:
                raise ValueError(f"Syntax Error, unknown {token=} at {lineno=}")


class Unary(BaseModel):
    type: t.Literal["COMPLEMENT", "MINUS"]
    exp: Factor


type Simple_Binary = t.Literal[
    "MINUS",
    "PLUS",
    "ASTERISK",
]

type Binary_Operation = (
    Simple_Binary
    | t.Literal[
        "FORWARD_SLASH",
        "PERCENT",
    ]
)

BINARY_OP_PRECEDENCE: dict[Binary_Operation, int] = {
    "MINUS": 45,
    "PLUS": 45,
    "ASTERISK": 50,
    "FORWARD_SLASH": 50,
    "PERCENT": 50,
}


class BinaryOp(BaseModel):
    type: Binary_Operation
    lhs: Expression
    rhs: Expression

    @t.override
    def __repr__(self):
        return f"({self.type} {repr(self.lhs.type)} {repr(self.rhs.type)})"


class Identifier(RootModel[str]):
    def __init__(self, tokens: lexer.Token_Lexed):
        token, identifier, _ = tokens
        assert token == "IDENTIFIER", "Not an identifier!"
        # TODO(Joaquim): Add asserts for forbidden identifiers
        # Stoping stuff like (True = False)
        return super().__init__(root=identifier)  # pyright: ignore[reportUnknownMemberType]
