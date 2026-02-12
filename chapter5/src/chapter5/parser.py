"""
AST Definition

New shit in underscore

```
<program> ::= <function>
<function> ::= "int" <identifier> "(" "void" ")" "{" _{<block-item>}_ "}"
_<block-item> ::= <statement> | <declaration>_
_<declaration> ::= "int" <identifier> ["=" <exp>] ";"_
<statement> ::= "return" <exp> ";" | <exp> ";" | ";"
<exp> ::= <factor> | <exp> <binop> <exp>
<factor> ::= <int> | <identifier> | <unop> <factor> | "(" <exp> ")"
<unop> ::= "-" | "~" | "!"
<binop> ::= "-" | "+" | "*" | "/" | "%" | "&&" | "||"
          | "==" | "!=" | "<" | "<=" | ">" | ">=" | "="
<identifier> ::= ? An identifier token ?
<int> ::= ? A constant token ?
```


```pseudo-code:

parse_function_definition(tokens):
    // parse everything up through the open brace as before...
    --snip--
    function_body = []
    while peek(tokens) != "}":
        next_block_item = parse_block_item(tokens)
        function_body.append(next_block_item)
    take_token(tokens)
    return Function(name, function_body)


parse_exp(tokens, min_prec):
    left = parse_factor(tokens)
    next_token = peek(tokens)
    while next_token is a binary operator and precedence(next_token) >= min_prec:
        # This stuff is new!
        if next_token is "=":
            take_token(tokens) // remove "=" from list of tokens
            right = parse_exp(tokens, precedence(next_token))
            left = Assignment(left, right)
        else:
            operator = parse_binop(tokens)
            right = parse_exp(tokens, precedence(next_token) + 1)
            left = Binary(operator, left, right)
        next_token = peek(tokens)
    return left
```

Notes:

> While parsing <block-item>, you need a way to tell whether the current block
> item is a statement or a declaration. To do this, peek at the first token; if
> it’s the int keyword, it’s a declaration, and otherwise it’s a statement.

"""

from textwrap import dedent
import typing as t

from pydantic import BaseModel, RootModel

from chapter5 import lexer
import shared.pure_functions as pf
import shared.data_types as dt


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
    body: list[BlockItem]

    @t.override
    def __repr__(self):
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
        with pf.set_context(dt.INDENT_LEVEL, dt.INDENT_LEVEL.get() + 2):
            body = pf.indent("\n".join(repr(b) for b in self.body))

        return f"{start}{body})"

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

        closing_bracket_index = get_closing(rest, "}")

        assert not rest[closing_bracket_index + 1 :], (
            "How the heck is there more stuff after the last bracket?"
        )

        body = rest[0:closing_bracket_index]
        parsed_body: list[BlockItem] = []

        while body:
            block_item = Declaration.get_next(body) or Statement.get_next(body)
            if block_item is None:
                raise ValueError("I accept declarations or statements!")
            item, body = block_item
            parsed_body.append(item)

        return super().__init__(
            return_type=CType(type),
            name=Identifier(identifier),
            body=parsed_body,
        )


type BlockItem = Statement | Declaration


class Declaration(BaseModel):
    """
    <declaration> ::= "int" <identifier> ["=" <exp>] ";"_
    """

    type: CType
    name: Identifier
    init: Expression | None

    @t.override
    def __repr__(self):
        pre = f"(let {repr(self.name)}:{self.type.root}"
        if not self.init:
            return pre + ")"
        return f"{pre} '{self.init or 'void'})"

    @staticmethod
    def get_next(tokens: lexer.Lexed) -> tuple[Declaration, lexer.Lexed] | None:
        if len(tokens) < 2:
            return None
        type, identifier, *rest = tokens

        ctype = pf.try_model(CType, token=type)
        name = pf.try_model(Identifier, token=identifier)

        if ctype is None or name is None:
            return None

        (next_token, *_), *rest = rest
        match next_token:
            case "=":
                exp, rest = Expression.parse(rest)

                (semicolon, *_), *rest = rest
                assert semicolon == "SEMICOLON", "Missing semicolon!"

                return Declaration(type=ctype, name=name, init=exp), rest
            case "SEMICOLON":
                return Declaration(type=ctype, name=name, init=None), rest
            case _:
                raise ValueError("Syntax error!")


class CType(RootModel[str]):
    def __init__(self, token: lexer.Token_Lexed):
        assert token[0] == "INT_KEYWORD", "I know of no other CTypes! Sorry"
        assert token[1] == "int"
        return super().__init__(root=token[1])  # pyright: ignore[reportUnknownMemberType]


class ReturnStatement(BaseModel):
    exp: Expression

    @t.override
    def __repr__(self):
        return f"(return {repr(self.exp)})"


class IfStatement(BaseModel):
    condition: Expression
    else_s: "Statement | None" = None

    def __init__(self, tokens: lexer.Lexed):
        super().__init__(condition="xD")
        raise NotImplementedError


class Statement(BaseModel):
    """
    <statement> ::= "return" <exp> ";" | <exp> ";" | ";"
    """

    root: ReturnStatement | Expression | t.Literal["nope"]

    @t.override
    def __repr__(self):
        return repr(self.root)

    @staticmethod
    def get_next(tokens: lexer.Lexed) -> tuple[Statement, lexer.Lexed] | None:
        (next_token, *_), *rest = tokens

        if next_token == "SEMICOLON":
            # ok
            return Statement(root="nope"), rest

        if next_token == "RETURN_KEYWORD":
            exp, rest = Expression.parse(rest)

            (semicolon, *_), *rest = rest
            assert semicolon == "SEMICOLON", "Missing semicolon!"
            return Statement(root=ReturnStatement(exp=exp)), rest

        # Well then it must be an expression followed b a semicolon
        exp, rest = Expression.parse(tokens)

        (semicolon, *_), *rest = rest
        assert semicolon == "SEMICOLON", "Missing semicolon!"
        return Statement(root=exp), rest


class Expression(BaseModel):
    type: BinaryOp | Factor | Assignment

    @t.override
    def __repr__(self):
        return repr(self.type)

    @t.overload
    @staticmethod
    def parse(
        tokens: lexer.Lexed,
        assert_no_food_left: t.Literal[False] = False,
        min_prec: int = 0,
    ) -> tuple[Expression, lexer.Lexed]: ...

    @t.overload
    @staticmethod
    def parse(
        tokens: lexer.Lexed, assert_no_food_left: t.Literal[True], min_prec: int = 0
    ) -> Expression:
        """
        If we specify `assert_no_food_left` then we assert that the tokens we _would_ return are empty.
        """

    @staticmethod
    def parse(
        tokens: lexer.Lexed, assert_no_food_left: bool = False, min_prec: int = 0
    ) -> tuple[Expression, lexer.Lexed] | Expression:
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

                # RIGHT ASSOCIATIVITY VS LEFT ASSOCIATIVITY
                # See chapter5/README.md
                if operator == "=":
                    # special case!
                    rhs, other_rest = inner(rest, BINARY_OP_PRECEDENCE[operator])
                    left = Assignment(lhs=Expression(type=left), rhs=rhs)
                else:
                    # Don't quite understand this +1 if I must be honest
                    rhs, other_rest = inner(rest, BINARY_OP_PRECEDENCE[operator] + 1)
                    left = BinaryOp(type=operator, lhs=Expression(type=left), rhs=rhs)
                right = other_rest

            return Expression(type=left), right

        exp, rest = inner(tokens, min_prec)
        if assert_no_food_left:
            assert rest == [], "We left food on the table!"
            return exp
        return exp, rest


class Constant(RootModel[int]):
    pass


class Factor(BaseModel):
    """
    The name `factor` comes from the fact that this symbol can appear as a
    _factor_ in a multiplication expression.

    """

    type: Constant | Unary | Expression | Identifier

    @t.override
    def __repr__(self):
        match self.type:
            case Constant():
                return repr(self.type.root)
            case Unary():
                return f"({self.type.type} {repr(self.type.exp)})"
            case Expression() | Identifier():
                return repr(self.type)

    @staticmethod
    def parse(tokens: lexer.Lexed) -> tuple[Factor, lexer.Lexed]:
        (token, identifier, lineno), *rest = tokens
        match token:
            case "IDENTIFIER":
                return Factor(
                    type=Identifier((token, identifier, lineno)),
                ), rest
            case "CONSTANT":
                return Factor(
                    type=Constant(identifier),  # pyright: ignore[reportArgumentType]
                ), rest
            case "OPEN_PARENS":
                corresponding_closed = get_closing(tokens[1:], ")")

                return Factor(
                    type=Expression.parse(
                        tokens[1 : corresponding_closed + 1], assert_no_food_left=True
                    )
                ), tokens[corresponding_closed + 2 :]

            case "COMPLEMENT" | "MINUS" | "NOT":
                exp, rest = Factor.parse(rest)
                return Factor(
                    type=Unary(type=token, exp=exp),
                ), rest
            case _:
                raise ValueError(f"Syntax Error, unknown {token=} at {lineno=}")


class Unary(BaseModel):
    type: t.Literal[
        "COMPLEMENT",
        "MINUS",
        "NOT",
    ]
    exp: Factor


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

type Assignment_Operator = t.Literal["="]

type Binary_Operation = (
    Simple_Binary
    | Relational_Binary
    | t.Literal[
        "FORWARD_SLASH",
        "PERCENT",
    ]
    | Jumpy_Binary_Op
    | Assignment_Operator
)


def _binary_op_precedence(op: Binary_Operation):
    """
    The reference is:
    https://en.cppreference.com/w/c/language/operator_precedence.html

    The code expects that higher -> more priority (reverse of the above reference)
    So we just subtract some large number and we're off to the races

    Note: We use a `match` just so that we don't forget any literal.
    Type-checkers will then have our back.

    """
    match op:
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
        case "=":
            return 100 - 14


BINARY_OP_PRECEDENCE: dict[Binary_Operation, int] = {
    op: _binary_op_precedence(op)
    for op in t.cast(frozenset[Binary_Operation], pf.get_literal_vals(Binary_Operation))
}


class BinaryOp(BaseModel):
    type: Binary_Operation
    lhs: Expression
    rhs: Expression

    @t.override
    def __repr__(self):
        return f"({self.type} {repr(self.lhs.type)} {repr(self.rhs.type)})"


class Assignment(BaseModel):
    lhs: Expression
    rhs: Expression

    @t.override
    def __repr__(self):
        return f"(= {repr(self.lhs.type)} {repr(self.rhs.type)})"


class Identifier(RootModel[str]):
    def __init__(self, token: lexer.Token_Lexed):
        ltoken, identifier, _ = token
        assert ltoken == "IDENTIFIER", "Not an identifier!"
        # TODO(Joaquim): Add asserts for forbidden identifiers
        # Stoping stuff like `True = False`
        # Use pydantic
        return super().__init__(root=identifier)  # pyright: ignore[reportUnknownMemberType]

    @t.override
    def __repr__(self):
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
