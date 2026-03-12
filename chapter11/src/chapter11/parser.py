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

import typing as t
from contextlib import suppress

import shared.data_types as dt
import shared.pure_functions as pf
from pydantic import BaseModel, Field, RootModel, model_validator

from chapter11 import lexer


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

        while tokens:
            (next_token, token, *_), *rest = tokens
            match next_token:
                case "INT_KEYWORD" | "LONG_KEYWORD":
                    types.append(CType.from_token((next_token, token, *_)))  # pyright: ignore[reportArgumentType]
                    tokens = rest
                case "EXTERN_KEYWORD" | "STATIC_KEYWORD":
                    # pydantic will catch us if we goof here
                    storage_classes.append(token)  # pyright: ignore[reportArgumentType]
                    tokens = rest
                case "IDENTIFIER":
                    # We're done here!
                    break
                case _:
                    raise ValueError(f"What is this {next_token=} doing here bro?")

        # Technically - the types can be automatically inferred to be 'int'
        # But the book says to just enforce it
        # We also don't do `auto`
        assert len(types) <= 2 and len(types) >= 1, "Bro!"

        if len(types) == 2:
            # shit! It's weird but it's OK to define a long as
            # int static long
            as_set = {str(t.root.root) for t in types}  # pyright: ignore[reportAttributeAccessIssue, reportUnknownArgumentType, reportUnknownMemberType]
            assert as_set == {"long", "int"}
            types = [CType(root=TrivialType(root="long"))]

        assert len(storage_classes) <= 1, "BRO!"

        storage_class = None if not storage_classes else storage_classes[0]

        return (types[0], storage_class), tokens


def declaration_from_tokens(tokens: lexer.Lexed) -> tuple[Declaration, lexer.Lexed]:
    assert len(tokens) >= 3, "not enough tokens mannn!"

    (ctype, storage), rest = Specifiers.from_tokens(tokens)
    identifier, *rest = rest

    name = Identifier.from_tokens(identifier)

    (next_token, *_), *rest = rest
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
            raise ValueError("Syntax error!")


class Function_Declaration(BaseModel):
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
                    type=ctype, name=identifier, storage=None, init=None
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


class Variable_Declaration(BaseModel):
    """
    <variable-declaration> ::= "int" <identifier> ["=" <exp>] ";"_
    """

    type: CType
    name: Identifier
    init: Expression | None
    storage: Specifiers.Storage_Class | None

    @t.override
    def __str__(self):
        pre = f"(let {self.name!s}:{self.type.root}"
        return f"{pre} {self.init or 'undefined'})"


class Labelled_Construct(BaseModel):
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
            root=For(init=init_exp, condition=condition_exp, post=post_exp, body=body)
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
        with suppress(ValueError, AssertionError):
            decl, rest = declaration_from_tokens(tokens)
            assert isinstance(decl, Variable_Declaration), (
                "why you declaring a function here?"
            )
            # It's very easy to catch this error here
            # But the book expects us to catch them on the semantic-analysis phase
            # assert decl.storage is None, "For-Init can't have a storage class bro"
            assert rest == [], "We left food on the table!"
            return decl
        tokens_sans_semicolon = tokens[:-1]
        # If it's not a declaration it's _GOT_ to be an expression
        return Expression.from_tokens(tokens_sans_semicolon, assert_no_food_left=True)


class TrivialType(BaseModel):
    type SubType = t.Literal["int", "long"]
    root: SubType

    @staticmethod
    def from_tokens(token: lexer.Token_Lexed):
        return TrivialType(root=token[1])  # pyright: ignore[reportArgumentType]


class CType(BaseModel):
    class FuncType(BaseModel):
        return_type: CType
        params: list[CType]

    root: TrivialType | FuncType

    @staticmethod
    def from_trivial(which: TrivialType.SubType):
        return CType(root=TrivialType(root=which))

    @staticmethod
    def from_token(token: lexer.Token_Lexed):
        # This is wrong. But whatever
        return CType(root=TrivialType.from_tokens(token))

    @t.override
    def __str__(self):
        match self.root:
            case TrivialType():
                return str(self.root.root)
            case CType.FuncType():
                return f"('return {self.root.return_type.root} '(params ({', '.join(str(p) for p in self.root.params)})))"


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
        (next_token, *_), *rest = tokens

        def get_back_expression():
            # Well then it must be an expression followed by a semicolon
            exp, rest = Expression.from_tokens(tokens)

            (semicolon, *_), *rest = rest
            assert semicolon == "SEMICOLON", "Missing semicolon!"
            return Statement(root=exp), rest

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
                assert inner_expr, "We need an expression for the while!"
                assert after, "A while needs a statement brother!"
                condition = Expression.from_tokens(inner_expr, assert_no_food_left=True)
                body, rest = Statement.from_tokens(after)
                return (
                    Statement(root=While(condition=condition, body=body)),
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
                    Statement(root=DoWhile(condition=condition, body=body)),
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
                            condition=expression, then=then_stmt, else_s=else_stmt
                        )
                    ),
                    rest,
                )

            case "GOTO":
                identifier, *rest = rest
                assert identifier[0] == "IDENTIFIER", (
                    "After a `goto` we need an identifier!"
                )
                stmt = Statement(root=Goto(label=Identifier.from_tokens(identifier)))
                return stmt, _next_is_semicolon(rest)
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

            case "SWITCH_KEYWORD":
                switch, rest = Switch.from_tokens(rest)
                return Statement(root=switch), rest
            case "CASE_KEYWORD" | "DEFAULT_KEYWORD":
                case, rest = SwitchCase.from_tokens(tokens)
                return Statement(root=case), rest
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

        while tokens:
            item, tokens = Block.block_item_from_tokens(tokens)

            parsed_body.append(item)

        return Block(body=parsed_body)

    @staticmethod
    def block_item_from_tokens(tokens: lexer.Lexed) -> tuple[Block_Item, lexer.Lexed]:
        block_item: tuple[Block_Item, lexer.Lexed] | None = None
        with suppress(ValueError, AssertionError):
            block_item = declaration_from_tokens(tokens)
        with suppress(ValueError, AssertionError):
            block_item = Statement.from_tokens(tokens)
        if block_item is None:
            raise ValueError("I accept declarations or statements!")
        return block_item


class Typed(BaseModel):
    type: CType | None = None


class Expression(Typed):
    """
    <exp> ::= <factor> | <exp> <binop> <exp> | <exp> "?" <exp> ":" <exp>
    """

    type SubType = BinaryOp | Factor | FancyAssignment | NormalAssigment | Conditional
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
            _ = self.get_const_expression()
            return True
        return False

    def get_const_expression(self):
        match self.root:
            case Factor(root=Constant(root=root)):
                return root
            # TODO: Stuff like `int a = 1;`
            # is valid if `a` is `const` or the compiler can tell
            # that no one else touched it
            # For now - imma just not care
            case _:
                raise ValueError("Not a const expression bro!")

    @staticmethod
    def from_constant(const: int, ctype: TrivialType):
        return Expression(root=Factor(root=Constant(root=const, ctype=ctype)))

    @staticmethod
    def read_var(name: str):
        return Expression(root=Factor(root=Identifier(name)))

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

                    identifier = Expression(root=left)
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
                        left=Expression(root=left), middle=middle, right=right
                    )

                else:
                    # Don't quite understand this +1 if I must be honest
                    rhs, other_rest = inner(rest, BINARY_OP_PRECEDENCE[operator] + 1)
                    left = BinaryOp(
                        op=operator,  # pyright: ignore[reportArgumentType]
                        lhs=Expression(root=left),
                        rhs=rhs,
                    )
                right = other_rest

            return Expression(root=left), right

        exp, rest = inner(tokens, min_prec)
        if assert_no_food_left:
            assert rest == [], "We left food on the table!"
            return exp
        return exp, rest


class Constant(BaseModel):
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
            return Constant(root=v, ctype=TrivialType(root="long"))

        return Constant(root=v, ctype=TrivialType(root="int"))


class Factor(Typed):
    """
    The name `factor` comes from the fact that this symbol can appear as a
    _factor_ in a multiplication expression.

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
        match token:
            case "IDENTIFIER":
                ident = Identifier.from_tokens((token, identifier, charno))
                if not rest or rest[0][0] != "OPEN_PARENS":
                    # It's just an identifier
                    return (
                        Factor(root=ident),
                        rest,
                    )

                _, *rest = rest
                corresponding_closed = get_closing(rest, ")")
                arg_list = Func_Call.args_from_tokens(rest[:corresponding_closed])

                return (
                    Factor(root=Func_Call(name=ident, args=arg_list)),
                    rest[corresponding_closed + 1 :],
                )
            case "CONSTANT" | "LONG_CONSTANT":
                return (
                    Factor(
                        root=Constant.from_token(
                            (token, identifier, charno),  # pyright: ignore[reportArgumentType]
                        ),
                    ),
                    rest,
                )
            case "OPEN_PARENS":
                if rest[0][0] in ("INT_KEYWORD", "LONG_KEYWORD"):
                    # shoot, it's a cast!
                    cast, rest = Cast.from_tokens(rest)
                    return Factor(root=cast), rest
                corresponding_closed = get_closing(rest, ")")
                return (
                    Factor(
                        root=Expression.from_tokens(
                            rest[:corresponding_closed], assert_no_food_left=True
                        )
                    ),
                    rest[corresponding_closed + 1 :],
                )

            case "COMPLEMENT" | "MINUS" | "NOT" | "++" | "--":
                exp, rest = Factor.parse(rest)
                return (
                    Factor(
                        root=Unary(op=token, exp=exp),
                    ),
                    rest,
                )
            case _:
                pass
        raise AssertionError(f"Syntax Error, unknown {token=} at {charno=}")


class Func_Call(BaseModel):
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


class Cast(BaseModel):
    target_type: CType
    exp: Expression

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> tuple[Cast, lexer.Lexed]:
        """
        Note: That the opening parens has been consumed
        """
        corresponding_closed = get_closing(tokens, ")")
        (ctype, specifier), nada = Specifiers.from_tokens(tokens[:corresponding_closed])
        assert specifier is None and nada == [], "Failed to parse type of cast!"

        exp, rest = Expression.from_tokens(tokens[corresponding_closed + 1 :])

        return Cast(target_type=ctype, exp=exp), rest

    @t.override
    def __str__(self):
        return f"(cast-to-{self.target_type} {self.exp})"


class Unary(BaseModel):
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
    op: Binary_Op_Without_Assignment
    lhs: Expression
    rhs: Expression

    @t.override
    def __str__(self):
        return f"({self.op} {self.lhs.root!s} {self.rhs.root!s})"


class NormalAssigment(BaseModel):
    lhs: LValue
    rhs: Expression

    @t.override
    def __str__(self):
        return f"(= {self.lhs!s} {self.rhs.root!s})"


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
        return f"({self.type} {self.lhs!s} {self.rhs.root!s})"


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
        closing_parens = get_closing(tokens, ")")
        exp_tokens, rest = tokens[:closing_parens], tokens[closing_parens + 1 :]
        checker = Expression.from_tokens(exp_tokens, assert_no_food_left=True)
        stmt = Statement.from_tokens(rest)
        assert stmt is not None, "No body!"
        body, rest = stmt
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
        (keyword, *_), *rest = tokens
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
    for index, (_, lexed, _) in enumerate(tokens):
        if lexed not in (closing_symbol, open_symbol):
            continue
        if lexed == open_symbol:
            number_of_open += 1
            continue
        number_of_closed += 1
        assert number_of_open, "We closed without ever finding the opening symbol!"
        if number_of_closed == number_of_open:
            return index

    raise ValueError(f"Where's the '{closing_symbol}' brother?")
