"""
AST Definition

New shit in underscore

```
<program> ::= {<declaration>}
<declaration> ::= <variable-declaration> | <function-declaration>
<variable-declaration> ::= {<specifier>}+ <identifier> ["=" <exp>] ";"
<function-declaration> ::= {<specifier>}+ <identifier> "(" <param-list> ")" (<block> | ";")
_<type-specifier> ::= 'int' | 'long'_
_<specifier> ::= <type-specifier> | "static" | "extern"_
_<param-list> ::= "void" | <type-specifier>+ <identifier> {"," <type-specifier>+ <identifier>}_
<block> ::= "{" {<block-item} "}"
<block-item> ::= <statement> | <declaration>
<declaration> ::= "int" <identifier> ["=" <exp>] ";"
<for-init> ::= <variable-declaration> | [<exp>] ";"
<statement> ::= "return" <exp> ";"
    | <exp> ";"
    | ";"
    | "if" "(" <exp> ")" <statement> ["else" <statement>]
    | goto <identifier>;
    | <identifier>: <statement>
    | <block>
    | "break" ";"
    | "continue" ";"
    | "while" "(" <exp> ")" <statement>
    | "do" <statement> "while" "(" <exp> ")" ";"
    | "for" "(" <for-init> [<exp>] ";" [<exp>] ")" <statement>
    | switch(<expression>) <statement>
    | <switchtype>
<switchtype> ::= case <constantexpression>: {<statement>} | default: {<statement>}
<constantexpression>  ::= <int>
<exp> ::= <factor> | <exp> <binop> <exp> | <exp> "?" <exp> ":" <exp>
<factor> ::= <const>
  | <identifier>
  | "(" {<type-specifier>}+ ")" <factor>
  | <unop> <factor>
  | <factor> <postop>
  | "(" <exp> ")"
  | <identifier> '(' [<argument-list>] ')'
<argument-list> ::= <exp> {"," <exp>}
<unop> ::= "-" | "~" | "!" | "++" | "--"
<postop> ::= "++" | "--"
<binop> ::= "-" | "+" | "*" | "/" | "%" | "&&" | "||"
          | "==" | "!=" | "<" | "<=" | ">" | ">=" | "="
          | "+=" | "-=" | "*=" | "%=" | "&=" | "|=" | "^=" | "<<=" | ">>="
<identifier> ::= ? An identifier token ?
<const> ::= <int> | <long>
<int> ::= ? A constant token ?
<long> ::= ? A constant token ?
```

Notes:

> While parsing <block-item>, you need a way to tell whether the current block
> item is a statement or a declaration. To do this, peek at the first token; if
> it's the int keyword, it's a declaration, and otherwise it's a statement.

"""

import re
import typing as t
from contextlib import suppress

import shared.data_types as dt
import shared.pure_functions as pf
from pydantic import AfterValidator, BaseModel, Field, RootModel, model_validator

from chapter11 import lexer


class HasLoc(BaseModel):
    location: lexer.Location = Field(default_factory=lexer.CURRENT_LOCATION.get)


class Program(BaseModel):
    """
    <program> ::= {<declaration>}
    """

    declarations: list[Declaration]

    @staticmethod
    def from_tokens(tokens: lexer.Lexed):
        declarations: list[Declaration] = []
        while tokens:
            decl, tokens = declaration_from_tokens(tokens)
            declarations.append(decl)
        return Program(declarations=declarations)

    @t.override
    def __str__(self):
        return "\n".join(map(str, self.declarations))


@t.final
class Specifiers:
    """

    <specifier> ::= <type-specifier> | "static" | "extern"
    <type-specifier> ::= "int" | "long"


    Returns the ctype and storage-class given some tokens.

    (In the book they have a separate `parse_types` function, but to me it seems simpler to just
    do it here, and instead we investigate if there should be a storage class later)

    Note: That these are equivalent

    ```c
    int static a = 3;
    static int a = 3;
    ```

    Weirdly, so are these

    ```c
    extern long int a = 4l;
    int extern long a = 4;
    ```
    """

    type Storage_Class = t.Literal["static", "extern"]

    @staticmethod
    def from_tokens(
        tokens: lexer.Lexed,
    ) -> tuple[tuple[CType, Specifiers.Storage_Class | None], lexer.Lexed]:
        types: list[
            CType
        ] = []  # it's a list, because `long int` and `long` and `int long` are equivalent
        storage_classes: list[Specifiers.Storage_Class] = []

        if tokens:
            _ = lexer.CURRENT_LOCATION.set(tokens[0][2])

        while tokens:
            (next_token, token, loc), *rest = tokens
            reset_token = lexer.CURRENT_LOCATION.set(loc)
            match next_token:
                case "INT_KEYWORD" | "LONG_KEYWORD":
                    types.append(CType.from_token((next_token, token, loc)))
                    tokens = rest
                case "EXTERN_KEYWORD" | "STATIC_KEYWORD":
                    # pydantic will catch us if we goof here
                    storage_classes.append(token)  # pyright: ignore[reportArgumentType]
                    tokens = rest
                case "IDENTIFIER":
                    # We're done here!
                    break
                case _:
                    raise ParseError(loc, f"What is this {next_token=} doing here bro?")
            lexer.CURRENT_LOCATION.reset(reset_token)

        # Technically - the types can be automatically inferred to be 'int'
        # But the book says to just enforce it
        # We also don't do `auto`
        if len(types) > 2 or len(types) < 1:
            raise ParseError(tokens[0][2], "Bro!")

        if len(types) == 2:
            # shit! It's weird but it's OK to define a long as
            # int static long
            as_set = {str(t.root) for t in types}
            if as_set != {"long", "int"}:
                raise ParseError(
                    tokens[0][2], "Bad types! We only accept int/long or long int"
                )
            types = [CType(root="long")]

        if len(storage_classes) > 1:
            raise ParseError(tokens[0][2], "BRO!")

        storage_class = None if not storage_classes else storage_classes[0]

        return (types[0], storage_class), tokens


def declaration_from_tokens(tokens: lexer.Lexed) -> tuple[Declaration, lexer.Lexed]:
    assert len(tokens) >= 3, "not enough tokens mannn!"

    (ctype, storage), rest = Specifiers.from_tokens(tokens)
    identifier, *rest = rest

    name = Identifier.from_tokens(identifier)

    (next_token, _, loc), *rest = rest
    _ = lexer.CURRENT_LOCATION.set(loc)
    match next_token:
        case "=":
            exp, rest = Expression.from_tokens(rest)
            return (
                Variable_Declaration(
                    type=ctype,
                    name=name,
                    init=exp,
                    storage=storage,
                ),
                _next_is_semicolon(rest),
            )
        case "SEMICOLON":
            return (
                Variable_Declaration(
                    type=ctype,
                    name=name,
                    storage=storage,
                    init=None,
                ),
                rest,
            )
        case "OPEN_PARENS":
            # It's a function
            closing_paren = get_closing(rest, ")", consumed_opening_symbol=True)
            param_list = Function_Declaration.get_param_list(rest[: closing_paren + 1])
            (next_token, *_), *rest = rest[closing_paren + 1 :]
            if next_token == "{":  # }
                closing_bracket_index = get_closing(rest, "}")
                body = Block.from_tokens(rest[:closing_bracket_index])
                rest = rest[closing_bracket_index + 1 :]
            else:
                assert next_token == "SEMICOLON", (
                    f"Nope, function must look like: {Function_Declaration.__doc__}"
                )
                body = None

            return (
                Function_Declaration(
                    type=CType.FuncType(
                        return_type=ctype,
                        params=[p.type for p in param_list],
                    ),
                    name=name,
                    body=body,
                    param_list=[p.name for p in param_list],
                    storage=storage,
                ),
                rest,
            )
        case _:
            raise ParseError(loc, "Syntax error!")


class Function_Declaration(HasLoc):
    """
    <function-declaration> ::= {<specifier>}+ <identifier> "(" <param-list> ")" (<block> | ";")
    """

    type: CType.FuncType
    name: Identifier
    param_list: list[Identifier]
    body: Block | None
    storage: Specifiers.Storage_Class | None

    @t.override
    def __str__(self):
        param_list = "'void"
        if self.param_list:
            param_list = str(
                {
                    param.root: str(self.type.params[index])
                    for index, param in enumerate(self.param_list)
                }
            ).replace("'", "")
            param_list = param_list.replace("'", "")

        with pf.set_context(dt.INDENT_LEVEL, 1):
            stuff = [
                f"('name {self.name})",
                f"('return_type {self.type.return_type})",
                f"('storage_class {self.storage})",
                f"('params {param_list})",
            ]
            start = f"(function {"'declaration" if not self.body else ''}\n{'\n'.join(map(pf.indent, stuff))}"

        if not self.body:
            return f"{start})"

        start = start + pf.indent("\n  ('body")

        with pf.set_context(dt.INDENT_LEVEL, 2):
            body = pf.indent(str(self.body))
        return f"{start}\n{body})"

    @staticmethod
    def get_param_list(tokens: lexer.Lexed):
        res: list[Variable_Declaration] = []
        rest: lexer.Lexed = tokens
        while rest:
            _ = lexer.CURRENT_LOCATION.set(rest[0][2])
            if rest[0][0] == "VOID_KEYWORD":
                # special case
                rest = _next_is(rest[1:], "CLOSE_PARENS")
                assert not res, "Can't mix and match void with other params!"
                break

            (ctype, storage_class), rest = Specifiers.from_tokens(rest)
            assert storage_class is None, (
                "function parameters can't have a storage class!"
            )
            identifier_token, *rest = rest
            identifier = Identifier.from_tokens(identifier_token)
            res.append(
                Variable_Declaration(
                    type=ctype,
                    name=identifier,
                    storage=None,
                    init=None,
                )
            )

            (next_token, *_), *rest = rest
            if next_token == "CLOSE_PARENS":
                break
            assert next_token == ","

        assert rest == [], "We left food on the table!"
        return res


type Block_Item = Statement | Declaration

type Declaration = Variable_Declaration | Function_Declaration


class Variable_Declaration(HasLoc):
    """
    <variable-declaration> ::= "int" <identifier> ["=" <exp>] ";"_
    """

    type: TrivialType
    name: Identifier
    init: Expression | None
    storage: Specifiers.Storage_Class | None

    @t.override
    def __str__(self):
        pre = f"(let {self.name!s}:{self.type.root}"
        return f"{pre} {self.init or 'undefined'})"


class Labelled_Construct(HasLoc):
    """
    Whenever we `continue/break` we need to know _which_ loop statement we're
    actually breaking from.

    Thus - the semantic analysis will just annotate each loop with some control
    label that we can jump out/in of.
    """

    control_label: str = ""


class Break(Labelled_Construct):
    @t.override
    def __str__(self):
        return f"(break {self.control_label if self.control_label else ''})"


class Continue(Labelled_Construct):
    @t.override
    def __str__(self):
        return f"(continue {self.control_label if self.control_label else ''})"


class While(Labelled_Construct):
    condition: Expression
    body: Statement

    @t.override
    def __str__(self):
        res = [
            f"(while {self.control_label if self.control_label else ''} {self.condition}"
        ]  # )

        with pf.set_context(dt.INDENT_LEVEL, 1):
            res.append(pf.indent(str(self.body)) + ")")

        return "\n".join(res)


class DoWhile(While):
    """
    Note: Uses inheritance! So be careful when using `match-case`
    """

    @t.override
    def __str__(self):
        res = [f"(do {self.control_label if self.control_label else ''}"]  # )

        with pf.set_context(dt.INDENT_LEVEL, 1):
            res.append(pf.indent(str(self.body)))
            res.append(pf.indent(f"(while {self.condition!s}))"))

        return "\n".join(res)


type For_Init = Variable_Declaration | Expression | None


class For(Labelled_Construct):
    """
    "for" "(" <for-init> [<exp>] ";" [<exp>] ")" <statement>
    """

    init: For_Init
    condition: Expression | None
    post: Expression | None
    body: Statement

    @t.override
    def __str__(self):
        res = f"(for {self.control_label if self.control_label else ''}\n"  # )

        with pf.set_context(dt.INDENT_LEVEL, 1):
            start = pf.indent(
                "\n".join(
                    [
                        f"(init {self.init})" if self.init else ";",
                        f"(condition {self.condition})" if self.condition else ";",
                        f"(post {self.post})" if self.post else ";",
                        "(body \n",  # )
                    ]
                )
            )
        with pf.set_context(dt.INDENT_LEVEL, 2):
            body = pf.indent(str(self.body))
        return f"{res}{start}{body})"

    @staticmethod
    def from_tokens(tokens: lexer.Lexed):
        rest = _next_is(tokens, "OPEN_PARENS")
        _ = lexer.CURRENT_LOCATION.set(tokens[0][2])

        first_closing = get_closing(rest, ";")
        # We _want_ to include the closing `;`
        # Just makes parsing for declarations easier
        init_tokens, rest = rest[: first_closing + 1], rest[first_closing + 1 :]
        init_exp: For_Init = For._get_for_init(init_tokens)

        second_closing = get_closing(rest, ";")
        condition_tokens, rest = (
            rest[:second_closing],
            rest[second_closing + 1 :],
        )
        condition_exp = (
            Expression.from_tokens(condition_tokens, assert_no_food_left=True)
            if condition_tokens
            else None
        )

        closed_parens = get_closing(rest, ")")

        post_tokens, rest = rest[:closed_parens], rest[closed_parens + 1 :]

        post_exp = (
            Expression.from_tokens(post_tokens, assert_no_food_left=True)
            if post_tokens
            else None
        )

        body, rest = Statement.from_tokens(rest)

        return Statement(
            root=For(
                init=init_exp,
                condition=condition_exp,
                post=post_exp,
                body=body,
            ),
        ), rest

    @staticmethod
    def _get_for_init(tokens: lexer.Lexed) -> For_Init:
        """
        Handles `(init_exp?;...)` section of the for-loop.

        Expects that the semicolon is passed
        """
        if not tokens or (len(tokens) == 1 and tokens[0][0] == "SEMICOLON"):
            # Perfectly valid
            # for(; 1 ;) {...}
            return None
        decl: Declaration | None = None
        stfu = pf.stfu(ValueError, AssertionError)
        with stfu:
            decl, rest = declaration_from_tokens(tokens)
            assert isinstance(decl, Variable_Declaration)
            # It's very easy to catch this error here
            # But the book expects us to catch them on the semantic-analysis phase
            # assert decl.storage is None, "For-Init can't have a storage class bro"
            assert rest == []
            return decl
        with stfu:
            tokens_sans_semicolon = tokens[:-1]  # pyright: ignore[reportUnreachable]
            # If it's not a declaration it's _GOT_ to be an expression
            return Expression.from_tokens(
                tokens_sans_semicolon, assert_no_food_left=True
            )

        raise ExceptionGroup("Failed to parse for-init!", stfu.caught)


type Trivial_SubType = t.Literal["int", "long"]


class CType(BaseModel):
    class FuncType(BaseModel):
        return_type: CType
        params: list[CType]

    root: Trivial_SubType | FuncType

    @staticmethod
    def from_token(token: lexer.Token_Lexed):
        return CType(root=token[1])  # pyright: ignore[reportArgumentType]

    @staticmethod
    def from_trivial(which: Trivial_SubType):
        return CType(root=which)

    @staticmethod
    def assert_is_trivial(ctype: t.Any) -> TrivialType:  # pyright: ignore[reportAny]
        assert ctype.is_trivial()  # pyright: ignore[reportAny]
        return ctype  # pyright: ignore[reportAny]

    def is_trivial(self: CType):
        return self.root in ("int", "long")

    def get_trivial(self) -> Trivial_SubType:
        _ = self.assert_is_trivial(self)
        return self.root  # pyright: ignore[reportReturnType]

    def get_size(self) -> dt.x64.Bit_Size:
        match self.root:
            case "int":
                return 32
            case "long":
                return 64
            case _:
                raise ValueError("WE DON'T DO FUNCTION POINTERS YET")

    @t.override
    def __str__(self):
        match self.root:
            case "int" | "long":
                return self.root
            case CType.FuncType():
                return f"('return {self.root.return_type.root} '(params ({', '.join(str(p) for p in self.root.params)})))"


type TrivialType = t.Annotated[CType, AfterValidator(CType.assert_is_trivial)]


class ReturnStatement(HasLoc):
    exp: Expression

    @t.override
    def __str__(self):
        return f"(return {self.exp!s})"


class IfStatement(HasLoc):
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


class Statement(HasLoc):
    """
    <statement> ::= "return" <exp> ";"
        | <exp> ";"
        | ";"
        | "if" "(" <exp> ")" <statement> ["else" <statement>]
        | goto <identifier>;
        | <identifier>: <statement>
        | <block>
        | "break" ";"
        | "continue" ";"
        | "while" "(" <exp> ")" <statement>
        | "do" <statement> "while" "(" <exp> ")" ";"
        | "for" "(" <for-init> [<exp>] ";" [<exp>] ")" <statement>
        | switch(<expression) '{' {<declaration>} {<switch_type>} '}'
    """

    root: (
        ReturnStatement
        | Expression
        | t.Literal["nope"]
        | Break
        | Continue
        | While
        | DoWhile
        | For
        | IfStatement
        | Goto
        | Label
        | Block
        | Switch
        | SwitchCase
    )

    @t.override
    def __str__(self):
        return str(self.root)

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> tuple[Statement, lexer.Lexed]:
        (next_token, _, loc), *rest = tokens

        _ = lexer.CURRENT_LOCATION.set(loc)

        def get_back_expression():
            # Well then it must be an expression followed by a semicolon
            exp, rest = Expression.from_tokens(tokens)

            (semicolon, _, loc), *rest = rest
            if semicolon != "SEMICOLON":
                raise ParseError(loc, "Missing semicolon!")

            return Statement(root=exp, location=tokens[0][2]), rest

        match next_token:
            case "SEMICOLON":
                return (
                    Statement(root="nope"),
                    rest,
                )
            case "BREAK_KEYWORD":
                return (
                    Statement(root=Break()),
                    _next_is_semicolon(rest),
                )
            case "CONTINUE_KEYWORD":
                return (
                    Statement(root=Continue()),
                    _next_is_semicolon(rest),
                )
            case "RETURN_KEYWORD":
                exp, rest = Expression.from_tokens(rest)
                return (
                    Statement(root=ReturnStatement(exp=exp)),
                    _next_is_semicolon(rest),
                )
            case "WHILE_KEYWORD":
                rest = _next_is(rest, "OPEN_PARENS")
                closed_parens = get_closing(rest, ")")
                inner_expr = rest[:closed_parens]
                after = rest[closed_parens + 1 :]
                if not inner_expr:
                    raise ParseError(loc, "We need an expression for the while!")
                if not after:
                    raise ParseError(loc, "A while needs a statement brother!")
                condition = Expression.from_tokens(inner_expr, assert_no_food_left=True)
                body, rest = Statement.from_tokens(after)
                return (
                    Statement(
                        root=While(condition=condition, body=body),
                    ),
                    rest,
                )
            case "DO_KEYWORD":
                body, rest = Statement.from_tokens(rest)
                rest = _next_is(
                    _next_is(rest, "WHILE_KEYWORD"),
                    "OPEN_PARENS",
                )
                closed_parens = get_closing(rest, ")")
                condition = Expression.from_tokens(
                    rest[:closed_parens],
                    assert_no_food_left=True,
                )
                rest = _next_is_semicolon(rest[closed_parens + 1 :])
                return (
                    Statement(
                        root=DoWhile(condition=condition, body=body, location=loc),
                        location=loc,
                    ),
                    rest,
                )
            case "FOR_KEYWORD":
                return For.from_tokens(rest)
            case "IF_KEYWORD":
                rest = _next_is(rest, "OPEN_PARENS")
                closed_parens = get_closing(rest, ")")
                expression = Expression.from_tokens(
                    rest[:closed_parens], assert_no_food_left=True
                )

                then_stmt, rest = Statement.from_tokens(rest[closed_parens + 1 :])
                else_stmt = None

                if rest and rest[0][0] == "ELSE_KEYWORD":
                    else_stmt, rest = Statement.from_tokens(rest[1:])
                return (
                    Statement(
                        root=IfStatement(
                            condition=expression,
                            then=then_stmt,
                            else_s=else_stmt,
                        ),
                    ),
                    rest,
                )

            case "GOTO":
                identifier, *rest = rest
                if identifier[0] != "IDENTIFIER":
                    raise ParseError(
                        identifier[2], "After a `goto` we need an identifier!"
                    )

                stmt = Statement(
                    root=Goto(label=Identifier.from_tokens(identifier), location=loc),
                )
                return stmt, _next_is_semicolon(rest)
            case "IDENTIFIER":
                (colon, _, loc), *maybe = rest
                # Labeled statement
                if colon == ":":
                    child = Statement.from_tokens(maybe)
                    child_stmt, rest = child
                    return Statement(
                        root=Label(
                            label=Identifier.from_tokens(tokens[0]),
                            statement=child_stmt,
                        ),
                    ), rest
                # probably an expression
                return get_back_expression()

            case "{":
                closing_bracket_index = get_closing(rest, "}")
                return Statement(
                    root=Block.from_tokens(
                        rest[0:closing_bracket_index],
                    ),
                ), rest[closing_bracket_index + 1 :]

            case "SWITCH_KEYWORD":
                switch, rest = Switch.from_tokens(rest)
                return Statement(root=switch), rest
            case "CASE_KEYWORD" | "DEFAULT_KEYWORD":
                case, rest = SwitchCase.from_tokens(tokens)
                return Statement(root=case), rest
            case _:
                # probably an expression
                return get_back_expression()


class Goto(HasLoc):
    label: Identifier

    @t.override
    def __str__(self):
        return f"(goto {self.label!s})"


class Label(HasLoc):
    label: Identifier
    statement: Statement

    @t.override
    def __str__(self):
        return f"(label {self.label!s}\n{pf.indent(str(self.statement))})"


class Block(HasLoc):
    body: list[Block_Item]

    @t.override
    def __str__(self):
        start = "(scope\n"
        with pf.set_context(dt.INDENT_LEVEL, 1):
            return f"{start}{pf.indent('\n'.join(str(b) for b in self.body))})"

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> Block:
        """
        Note: Assumes that we've removed the brackets!
        ```python
        >>> print(Block.from_tokens(lexer.lex('int foo = 1; return foo + 2;')))
        (scope
          (let `foo`:int '1)
          (return (PLUS `foo` 2)))
        >>> # Valid C but wrong!
        >>> # Bad! It's a block in a block
        >>> # The Semicolon being missing would be caught elsewhere.
        >>> print(Block.from_tokens(lexer.lex(' { int foo = 1; return foo + 2; }')))
        (scope
          (scope
            (let `foo`:int '1)
            (return (PLUS `foo` 2))))
        ```
        """
        parsed_body: list[Block_Item] = []
        if tokens:
            _ = lexer.CURRENT_LOCATION.set(tokens[0][2])

        while tokens:
            item, tokens = Block.block_item_from_tokens(tokens)

            parsed_body.append(item)

        return Block(body=parsed_body)

    @staticmethod
    def block_item_from_tokens(tokens: lexer.Lexed) -> tuple[Block_Item, lexer.Lexed]:
        stfu = pf.stfu(ValueError, AssertionError)

        with stfu:
            return declaration_from_tokens(tokens)
        with stfu:
            return Statement.from_tokens(tokens)  # pyright: ignore[reportUnreachable]

        raise ExceptionGroup("I accept declarations or statements!", stfu.caught)


class Typed(BaseModel):
    type: CType | None


class Expression(Typed, HasLoc):
    """
    <exp> ::= <factor> | <exp> <binop> <exp> | <exp> "?" <exp> ":" <exp>
    """

    type SubType = (
        BinaryOp | Factor | Fancy_Assignment | Normal_Assignment | Conditional
    )
    root: SubType

    @model_validator(mode="after")
    def fix_paren_jank(self):
        """
        Fixes situations like:

        ```c
        int a = ((((((((2))))))));
        ```
        """
        match self.root:
            case Factor(root=Expression(root=inner)):
                self.root = inner
            case _:
                pass
        return self

    def is_const_expression(self):
        """
        Technically - I'd like to just do this at parse-level (easily doable with Annotate and AfterValidator)
        But the *BOOK* wants me to do that only at semantic-analysis time.
        """
        with suppress(ValueError):
            _ = self.get_const_expression(cast_to=None)
            return True
        return False

    def get_const_expression(
        self, *, cast_to: Trivial_SubType | None, mutate: bool = False
    ):
        """
        I don't like this little `mutate` thing...but the printer was outputting wrong values
        It would be correct on the symbol-table, but not on the Variable_Declaration itself
        """

        def get_val() -> Constant:
            match self.root:
                case Factor(root=Constant()):
                    # I don't understand why this guy is bugging out here
                    res: Constant = self.root.root  # pyright: ignore[reportAssignmentType]

                    # 1. We shouldn't mutate
                    # 2. This should be done bellow in cast_val
                    # But cast-val is being a dick
                    if mutate and cast_to:
                        self.type = CType.from_trivial(cast_to)
                        self.root.type = CType.from_trivial(cast_to)
                        res.ctype = CType(root=cast_to)

                    return res
                # In the future this step will be more involved
                case _:
                    raise ValueError("Not a const expression bro!")

        def cast_val(val: Constant):
            if cast_to is None:
                # Nothing todo, handled elsewhere
                return val.root
            new_val = Constant.fit(val.root, cast_to)
            if mutate:
                val.root = new_val
            return new_val

        return cast_val(get_val())

    @staticmethod
    def from_constant(const: int, ctype: TrivialType):
        return Expression(
            root=Factor(
                root=Constant(root=const, ctype=ctype),
                type=ctype,
            ),
            type=ctype,
        )

    @staticmethod
    def read_var(name: str, type: CType | None):
        """
        In practise the CType should never be none
        """
        return Expression(
            root=Factor(
                root=Identifier(name),
                type=type,
            ),
            type=type,
        )

    @t.override
    def __str__(self):
        return str(self.root)

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
            _ = lexer.CURRENT_LOCATION.set(tokens[0][2])
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
                        type=None,
                        root=Unary(
                            op=operator,
                            exp=left,  # pyright: ignore[reportArgumentType]
                            pre=False,
                        ),
                    )

                # RIGHT ASSOCIATIVITY VS LEFT ASSOCIATIVITY
                # See chapter5/README.md
                elif operator in lexer.ASSIGNMENT_OPS:
                    # special case!
                    rhs, other_rest = inner(rest, BINARY_OP_PRECEDENCE[operator])

                    identifier = Expression(root=left, type=None)
                    left = (
                        Fancy_Assignment(lhs=identifier, rhs=rhs, type=operator)
                        if operator != "="
                        else Normal_Assignment(lhs=identifier, rhs=rhs)
                    )
                elif operator == "?":
                    middle, rhs = inner(rest, 0)
                    (colon, _, loc), *rhs = rhs
                    if colon != ":":
                        raise ParseError(loc, "BAD IF EXPRESSION")
                    right, other_rest = inner(rhs, BINARY_OP_PRECEDENCE[operator])
                    left = Conditional(
                        left=Expression(root=left, type=None),
                        middle=middle,
                        right=right,
                    )

                else:
                    # Don't quite understand this +1 if I must be honest
                    rhs, other_rest = inner(rest, BINARY_OP_PRECEDENCE[operator] + 1)
                    left = BinaryOp(
                        op=operator,  # pyright: ignore[reportArgumentType]
                        lhs=Expression(root=left, type=None),
                        rhs=rhs,
                    )
                right = other_rest

            return Expression(root=left, type=None), right

        exp, rest = inner(tokens, min_prec)
        if assert_no_food_left:
            if rest:
                raise ParseError(rest[0][2], "We left food on the table!")
            return exp
        return exp, rest


class Constant(HasLoc):
    root: int
    ctype: TrivialType

    @t.override
    def __str__(self):
        return str(self.root)

    @staticmethod
    def from_token(token: lexer.Token):
        which_token = token[0]

        if which_token == "LONG_CONSTANT":
            # Removes the little `[lL]` from the string
            v = int(token[1][:-1])
        else:
            v = int(token[1])
        if v > 2**63 - 1:
            raise ValueError("{v=} can not be represented as int or long!")

        # If `v` is bigger than we expect it's a long
        # But the user can also specify `1l` to force it to be a long
        if which_token == "LONG_CONSTANT" or v > 2**31 - 1:
            return Constant(root=v, ctype=CType(root="long"))

        return Constant(root=v, ctype=CType(root="int"))

    @staticmethod
    def from_bool(bool: t.Literal[0, 1]):
        return Constant(root=int(bool), ctype=CType(root="int"))

    @staticmethod
    def fit(val: int, target: Trivial_SubType):
        """
        Given some infinite int - make it fit an int/long/etc
        """
        if val > dt.x64.max[64]:
            raise ValueError("{v=} can not be represented as int or long!")

        max_int = dt.x64.max[32]
        max_uint = dt.x64.umax[32]
        match target:
            case "long":
                return val
            case "int" if val > max_int:
                # We follow the rules as defined in GCC
                # This effectively `cuts` the first 4 bytes
                # (This `while` thing looks jank i gotta say)
                while val > max_int:
                    val = val - max_uint
                return val
            case "int":
                return val


class Factor(Typed, HasLoc):
    """
    The name `factor` comes from the fact that this symbol can appear as a
    _factor_ in a multiplication expression.

    TODO(Joaquim): Get _rid_ of this class.

    Instead there would be two functions for parsing expressions.
    """

    type SubType = Constant | Unary | Expression | Identifier | Func_Call | Cast
    root: SubType

    @t.override
    def __str__(self):
        match self.root:
            case Constant(root=root):
                return str(root)
            case _:
                return str(self.root)

    @staticmethod
    def parse(tokens: lexer.Lexed) -> tuple[Factor, lexer.Lexed]:
        (token, identifier, charno), *rest = tokens
        _ = lexer.CURRENT_LOCATION.set(charno)
        match token:
            case "IDENTIFIER":
                ident = Identifier.from_tokens((token, identifier, charno))
                if not rest or rest[0][0] != "OPEN_PARENS":
                    # It's just an identifier
                    return (
                        Factor(root=ident, type=None),
                        rest,
                    )

                _, *rest = rest
                corresponding_closed = get_closing(rest, ")")
                arg_list = Func_Call.args_from_tokens(rest[:corresponding_closed])

                return (
                    Factor(
                        root=Func_Call(name=ident, args=arg_list),
                        type=None,
                    ),
                    rest[corresponding_closed + 1 :],
                )
            case "CONSTANT" | "LONG_CONSTANT":
                return (
                    Factor(
                        root=Constant.from_token(
                            (token, identifier, charno),  # pyright: ignore[reportArgumentType]
                        ),
                        type=None,
                    ),
                    rest,
                )
            case "OPEN_PARENS":
                if rest[0][0] in ("INT_KEYWORD", "LONG_KEYWORD"):
                    # shoot, it's a cast!
                    cast, rest = Cast.from_tokens(rest)
                    return Factor(root=cast, type=None), rest
                corresponding_closed = get_closing(rest, ")")
                return (
                    Factor(
                        root=Expression.from_tokens(
                            rest[:corresponding_closed], assert_no_food_left=True
                        ),
                        type=None,
                    ),
                    rest[corresponding_closed + 1 :],
                )

            case "COMPLEMENT" | "MINUS" | "NOT" | "++" | "--":
                exp, rest = Factor.parse(rest)
                return (
                    Factor(
                        type=None,
                        root=Unary(op=token, exp=exp),
                    ),
                    rest,
                )
            case _:
                pass
        raise ParseError(charno, f"Syntax Error, unknown {token=}")


class Func_Call(HasLoc):
    name: Identifier
    args: list[Expression]

    @t.override
    def __str__(self):
        return f"({self.name} {' '.join(map(str, self.args) if self.args else '()')})"

    @staticmethod
    def args_from_tokens(tokens: lexer.Lexed):
        lst: list[Expression] = []
        while tokens:
            exp, tokens = Expression.from_tokens(tokens)
            lst.append(exp)
            if len(tokens) > 1:
                tokens = _next_is(tokens, ",")

        return lst


class Cast(HasLoc):
    target_type: CType
    exp: Expression

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> tuple[Cast, lexer.Lexed]:
        """
        Note: That the opening parens has been consumed
        """
        corresponding_closed = get_closing(tokens, ")")
        (ctype, specifier), nada = Specifiers.from_tokens(tokens[:corresponding_closed])

        if specifier is not None or nada != []:
            raise ParseError(tokens[0][2], "Failed to parse type of cast!")

        exp, rest = Expression.from_tokens(
            tokens[corresponding_closed + 1 :], min_prec=operator_precedence("CAST")
        )

        return Cast(target_type=ctype, exp=exp), rest

    @t.override
    def __str__(self):
        return f"(cast-to-{self.target_type} {self.exp})"


class Unary(HasLoc):
    op: t.Literal[
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
        return f"({self.op!s} {self.exp!s} {'' if self.pre else 'postfix'})"


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


def operator_precedence(op: Binary_Op_Or_Extras | t.Literal["CAST"]):
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
        # Prevents cases like (long) 2 == 3
        # Note that `cast` is not a TOKEN, it has to be manually inserted here
        # Quite annoying, but what can ya do
        case "CAST":
            return 100 - 2
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
    op: operator_precedence(op)
    for op in t.cast(
        frozenset[Binary_Op_Or_Extras], pf.get_literal_vals(Binary_Op_Or_Extras)
    )
}


class BinaryOp(HasLoc):
    op: Binary_Op_Without_Assignment
    lhs: Expression
    rhs: Expression

    @t.override
    def __str__(self):
        return f"({self.op} {self.lhs.root!s} {self.rhs.root!s})"


class Normal_Assignment(HasLoc):
    lhs: LValue
    rhs: Expression

    @t.override
    def __str__(self):
        return f"(= {self.lhs!s} {self.rhs.root!s})"


class Conditional(HasLoc):
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


class Fancy_Assignment(HasLoc):
    type: lexer.Fancy_Assignment_Ops
    lhs: LValue
    rhs: Expression

    @t.override
    def __str__(self):
        return f"({self.type} {self.lhs!s} {self.rhs.root!s})"

    def to_normal_assignment(self) -> Normal_Assignment:
        """
        Converts a fancy assignment into a normal one

        Note: `a %= 1` is the same as `a = a % 1`

        In ALMOST everyway. The only problem is that this nerd is not a valid lvalue
        """
        # pyright needed some help here
        rhs: Expression = self.rhs
        lhs = self.lhs
        type = self.type
        _ = lexer.CURRENT_LOCATION.set(self.location)

        def get_bin_op(op: Binary_Op_Without_Assignment):
            return Expression(
                type=None,
                root=BinaryOp(
                    op=op,
                    lhs=Expression(
                        root=Factor(root=lhs, type=None),
                        type=None,
                    ),
                    rhs=rhs,
                ),
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

        return Normal_Assignment(
            lhs=lhs,
            rhs=rhs,
        )


class Identifier(RootModel[str]):
    _location: lexer.Location = lexer.Location(0, 0)

    @property
    def location(self):
        return self._location

    @staticmethod
    def from_tokens(token: lexer.Token_Lexed):
        ltoken, identifier, loc = token
        if ltoken != "IDENTIFIER":
            raise ParseError(loc, "Not an identifier!")
        # TODO(Joaquim): Add asserts for forbidden identifiers
        # Stoping stuff like `True = False`
        # Use pydantic
        id = Identifier(identifier)
        id._location = loc
        return id

    @t.override
    def __str__(self):
        return f"`{self.root}`"

    @t.override
    def __hash__(self):
        return hash(f"IDENTIFIER_{self.root}")


class Switch(Labelled_Construct):
    """
    switch(<expression>) <statement>
    """

    checker: Expression
    body: Statement

    associated_cases: list[SwitchCase] = []
    """
    This field gets populated during the `semantic_analysis`
    Having explored godbolt the easiest way to convert this into IR is to
    do

    ```
    v = checker()
    if v == associated_cases[0]:
        jump 0
    if v == associated_cases[1]:
        jump 1
    ...etc
    else:
        jump default
    ```
    """

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> tuple[Switch, lexer.Lexed]:
        tokens = _next_is(tokens, "OPEN_PARENS")
        _ = lexer.CURRENT_LOCATION.set(tokens[0][2])
        closing_parens = get_closing(tokens, ")")
        exp_tokens, rest = tokens[:closing_parens], tokens[closing_parens + 1 :]
        checker = Expression.from_tokens(exp_tokens, assert_no_food_left=True)
        body, rest = Statement.from_tokens(rest)
        return Switch(checker=checker, body=body), rest

    @t.override
    def __str__(self):
        with pf.set_context(dt.INDENT_LEVEL, 1):
            body = pf.indent(f"('checker {self.checker})\n{self.body}")
        if self.associated_cases:
            with pf.set_context(dt.INDENT_LEVEL, 2):
                cases = pf.indent(
                    "\n".join(map(str, (c.type for c in self.associated_cases)))
                )
            body = pf.indent(f"'(associated_cases \n{cases})\n") + body
        return f"(switch \n{body})"


class SwitchCase(Labelled_Construct):
    """
    <switch_type>_ ::= case <constant_expression>: {<statement>} | default: {<statement>}
    """

    class Case(BaseModel):
        keyword: t.Literal["case"] = "case"
        check: Expression

        @t.override
        def __str__(self):
            return f"case '{self.check}"

    class Default(BaseModel):
        keyword: t.Literal["default"] = "default"

        @t.override
        def __str__(self):
            return "default"

    type: SwitchCase.Case | SwitchCase.Default = Field(discriminator="keyword")
    body: Statement
    label: Identifier = Identifier("")
    """
    This label is set during the semantic analysis
    """

    @t.override
    def __str__(self):
        with pf.set_context(dt.INDENT_LEVEL, 1):
            body = pf.indent(str(self.body))
        return (
            f"({self.type} {self.control_label if self.control_label else ''} \n{body})"
        )

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> tuple[SwitchCase, lexer.Lexed]:
        (keyword, _, loc), *rest = tokens
        _ = lexer.CURRENT_LOCATION.set(loc)
        assert keyword in ("DEFAULT_KEYWORD", "CASE_KEYWORD"), (
            "This should have been caught earlier brother!"
        )
        if keyword == "DEFAULT_KEYWORD":
            rest = _next_is(rest, ":")
            type = SwitchCase.Default()
        else:
            closing = get_closing(rest, ":")
            expression_tokens, rest = rest[:closing], rest[closing + 1 :]
            check = Expression.from_tokens(expression_tokens, assert_no_food_left=True)
            type = SwitchCase.Case(check=check)

        body, rest = Statement.from_tokens(rest)

        return SwitchCase(type=type, body=body), rest


def _next_is(tokens: lexer.Lexed, which: lexer.Token):
    try:
        (next, *_), *rest = tokens
        assert next == which
    except Exception as e:
        if tokens:
            raise ParseError(tokens[0][2], "Missing {which} bro!") from e
        raise AssertionError(f"Missing {which} bro!") from e
    return rest


def _next_is_semicolon(tokens: lexer.Lexed):
    return _next_is(tokens, "SEMICOLON")


def get_closing(
    tokens: lexer.Lexed,
    closing_symbol: t.Literal["}", ")", ";", ":"],
    *,
    consumed_opening_symbol: bool = True,
) -> int:
    """
    Given some opening symbol `(, {` find the closing symbol `) or }`.

    Also works with `;` and `:` for convenience with the `for` loop and the switch-case thing

    By default - assumes that we've already consumed one opening symbol
    """
    match closing_symbol:
        case "}":
            open_symbol = "{"  # }
        case ")":
            open_symbol = "("  # )
        case ";" | ":":
            open_symbol = None

    number_of_open = 1 if consumed_opening_symbol else 0
    number_of_closed = 0
    for index, (_, lexed, loc) in enumerate(tokens):
        if lexed not in (closing_symbol, open_symbol):
            continue
        if lexed == open_symbol:
            number_of_open += 1
            continue
        number_of_closed += 1
        if not number_of_open:
            raise ParseError(loc, "We closed without ever finding the opening symbol!")
        if number_of_closed == number_of_open:
            return index

    raise ParseError(tokens[0][2], f"Where's the '{closing_symbol}' brother?")


class ParseError(ValueError):
    def __init__(self, location: lexer.Location | None, msg: str, context: int = 2):
        if location is None:
            location = lexer.CURRENT_LOCATION.get()
        start = max(location.lineno - context, 0)
        end = location.lineno + context + 1
        errors = lexer.PRE_PROCESSED.get()[start:end]
        txt = [
            f"\n{lexer.FILENAME.get()}:{location.lineno}",
            "```",
        ]

        for index, context_lines in enumerate(errors, start=start):
            txt.append(context_lines)
            if index == location.lineno:
                m = re.search(r"^\s*", context_lines)
                if m:
                    neat_thing = f"┗{('┅' * (len(context_lines) - max(m.end(), 1)))}┛"
                    whitespace = context_lines[: max(m.end() - 1, 0)]
                    middle = len(neat_thing) // 2
                    neat_thing = neat_thing[:middle] + "┳" + neat_thing[middle + 1 :]
                    txt.append(f"{whitespace}{neat_thing}")
                    txt.append(f"{whitespace}{' ' * middle}┇")
                    txt.append(f"{whitespace}{' ' * middle}{msg}")
                else:
                    # SHOULD be unreachable...
                    # Suspicious...but whatever!
                    txt.append("┗" + "┅" * max(len(context_lines) - 2, 0) + "┛")

        txt.append("```")

        super().__init__("\n".join(txt))
