"""
AST Definition

As ASDL (Zephyr Abstract Syntax Description Language)

```
...same as chapt1
exp = Constant(int) | Unary(unary_operator, exp)
unary_operator = Complement | Negate
```
"""

import typing as t
from chapter2 import lexer

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


class Statement(RootModel[IfStatement | ReturnStatement]):
    def __init__(self, tokens: lexer.Lexed):
        return super().__init__(root=ReturnStatement(tokens))  # pyright: ignore[reportUnknownMemberType]


class Expression(BaseModel):
    has_parens: bool = False
    type: Constant | Unary

    @staticmethod
    def parse(tokens: lexer.Lexed) -> Expression:
        (token, identifier, lineno), *rest = tokens
        match token:
            case "CONSTANT":
                assert rest == [], "There should be nothing after the constant!"
                return Expression(type=Constant(identifier))  # pyright: ignore[reportArgumentType]
            case "OPEN_PARENS":
                # breakpoint()
                assert tokens[-1][0] == "CLOSE_PARENS", "Didn't close your parens bro"
                return Expression(
                    has_parens=True, type=Expression.parse(tokens[1:-1]).type
                )

            case "COMPLEMENT" | "NEGATION":
                return Expression(type=Unary(type=token, exp=Expression.parse(rest)))
            case _:
                raise ValueError(f"Syntax Error, unknown {token=} at {lineno=}")


class Constant(RootModel[int]):
    pass


class Unary(BaseModel):
    type: t.Literal["COMPLEMENT", "NEGATION"]
    exp: Expression


class Identifier(RootModel[str]):
    def __init__(self, tokens: lexer.Token_Lexed):
        token, identifier, _ = tokens
        assert token == "IDENTIFIER", "Not an identifier!"

        return super().__init__(root=identifier)  # pyright: ignore[reportUnknownMemberType]
