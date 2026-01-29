"""
AST Definition

As ASDL (Zephyr Abstract Syntax Description Language)

```
program = Program(function_definition)
function_definition = Function(identifier name, statement body)
statement = Return(exp) | If(exp condition, statement then, statement? else)
exp = Constant(int)
```

As a lisp?

```asdl
program = ('Program function_definition)
function_definition = ('Function ('identifier name) (statement body))
statement = (EITHER
                ('Return exp)
                ('If (exp condition) (statement then))
                ('If (exp condition) (statement then) (statement else)))
exp = ('Constant int)
```

Formal Grammar in (Backaus-Naur Form (EBNF)) notation

```
<program> ::= <function>
<function> ::= <CTYPE><identifier>"(""void"")""{"<statement>"}
<CTYPE> ::= 'int'
<statement>::= "return"<exp>";"| "if""("<exp>")"<statement>["else"<statement>]
<exp>::= <int>
<identifier>::= ? An identifier token ?
<int>::= ? A constant token ?
```

Symbols on the left (like `<function>`) are a non-terminal symbol.
Individual tokens (key-words, identifiers, punctuation, etc) are terminal symbols.
Note the jank `? plain text ?` notation. Indeed it's a plain ol' English of the
symbol; this is because they're not fixed strings.
"""

from chapter1 import lexer

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
        (_, return_token, _), exp, (_, semicolon, _), *rest = tokens
        assert return_token == "return", "Where's the 'return' brother?"
        assert semicolon == ";", "Where's the ';' brother?"
        assert not rest, "Found something after the semi-colon!"

        return super().__init__(exp=Expression(exp))


class IfStatement(BaseModel):
    condition: Expression
    else_s: "Statement | None" = None

    def __init__(self, tokens: lexer.Lexed):
        super().__init__(condition="xD")
        raise NotImplementedError


class Statement(RootModel[IfStatement | ReturnStatement]):
    def __init__(self, tokens: lexer.Lexed):
        return super().__init__(root=ReturnStatement(tokens))  # pyright: ignore[reportUnknownMemberType]


class Expression(RootModel[int]):
    def __init__(self, tokens: lexer.Token_Lexed):
        token, identifier, _ = tokens
        assert token == "CONSTANT", "The only expression I know are constants"

        return super().__init__(root=identifier)  # pyright: ignore[reportArgumentType, reportUnknownMemberType]


class Identifier(RootModel[str]):
    def __init__(self, tokens: lexer.Token_Lexed):
        token, identifier, _ = tokens
        assert token == "IDENTIFIER", "Not an identifier!"

        return super().__init__(root=identifier)  # pyright: ignore[reportUnknownMemberType]
