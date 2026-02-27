"""
AST Definition

New shit in underscore

```
_<program> ::= {<function-declaration>}_
_<declaration> ::= <variable-declaration> | <function-declaration>_
_<variable-declaration> ::= "int" <identifier> ["=" <exp>] ";"_
_<function-declaration> ::= "int" <identifier> "(" <param-list> ")" (<block> | ";")_
_<param-list> ::= "void" | "int" <identifier> {"," "int" <identifier>}_
<block> ::= "{" {<block-item} "}"
<block-item> ::= <statement> | <declaration>
<declaration> ::= "int" <identifier> ["=" <exp>] ";"
<for-init> ::= _<variable-declaration>_ | [<exp>] ";"
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
<factor> ::= <int>
  | <identifier>
  | <unop> <factor>
  | <factor> <postop>
  | "(" <exp> ")"
  | _<identifier> '(' [<argument-list>] ')'_
_<argument-list> ::= <exp> {"," <exp>}_
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
> it’s the int keyword, it’s a declaration, and otherwise it’s a statement.

"""

import typing as t
from contextlib import suppress

import shared.data_types as dt
import shared.pure_functions as pf
from pydantic import BaseModel, Field, RootModel, model_validator

from chapter9 import lexer


class Program(BaseModel):
    """
    <program> ::= <function>
    """

    functions: list[Function_Declaration]

    @staticmethod
    def from_tokens(tokens: lexer.Lexed):
        funcs: list[Function_Declaration] = []
        while tokens:
            func, tokens = Function_Declaration.from_tokens(tokens)
            funcs.append(func)
        return Program(functions=funcs)

    @t.override
    def __str__(self):
        return "\n".join(map(str, self.functions))


class Function_Declaration(BaseModel):
    """
    <function-declaration> ::= "int" <identifier> "(" <param-list> ")" (<block> | ";")
    """

    return_type: CType
    name: Identifier
    param_list: list[Variable_Declaration]
    body: Block | None

    @model_validator(mode="after")
    def ensure_no_init_in_param_list(self):
        for param in self.param_list:
            assert param.init is None, "In C you can't give a variable a default!"
        return self

    @t.override
    def __str__(self):
        param_list = "'void"
        if self.param_list:
            param_list = str(
                {param.name.root: param.type.root for param in self.param_list}
            ).replace("'", "")
            param_list = param_list.replace("'", "")

        with pf.set_context(dt.INDENT_LEVEL, 1):
            start = (
                f"(function {"'declaration" if not self.body else ''}\n"
                + "\n".join(
                    map(
                        pf.indent,
                        [
                            f"('name {self.name})",
                            f"('return_type {self.return_type.root})",
                            f"('params {param_list})",
                        ],
                    )
                )
            )

        if not self.body:
            return start

        start = start + pf.indent("\n  ('body")

        with pf.set_context(dt.INDENT_LEVEL, 2):
            body = pf.indent(str(self.body))
        return f"{start}\n{body})"

    @staticmethod
    def from_tokens(tokens: lexer.Lexed) -> tuple[Function_Declaration, lexer.Lexed]:
        try:
            (
                type,
                identifier,
                *rest,
            ) = tokens

        except ValueError as e:
            raise ValueError(
                f"Nope, function must look like: {Function_Declaration.__doc__}"
            ) from e

        closing_paren = get_closing(rest, ")", consumed_opening_symbol=False)
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
                return_type=CType.from_tokens(type),
                name=Identifier.from_tokens(identifier),
                body=body,
                param_list=param_list,
            ),
            rest,
        )

    @staticmethod
    def get_param_list(tokens: lexer.Lexed):
        res: list[Variable_Declaration] = []
        rest: lexer.Lexed
        (parens, *_), *rest = tokens
        assert parens == "OPEN_PARENS", "Where's the ( brother?"  # )
        while rest:
            type_token, *rest = rest
            if type_token[0] == "VOID_KEYWORD":
                rest = _next_is(rest, "CLOSE_PARENS")
                assert not res, "Can't mix and match void with other params!"
                break
            ctype = CType.from_tokens(
                type_token
            )  # will throw error if it's not correct
            identifier_token, *rest = rest
            identifier = Identifier.from_tokens(identifier_token)
            res.append(Variable_Declaration(type=ctype, name=identifier, init=None))

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

    @t.override
    def __str__(self):
        pre = f"(let {str(self.name)}:{self.type.root}"
        return f"{pre} {self.init or 'undefined'})"

    @staticmethod
    def from_tokens(
        tokens: lexer.Lexed,
    ) -> tuple[Variable_Declaration, lexer.Lexed]:
        assert len(tokens) >= 3, "not enough tokens mannn!"

        type, identifier, *rest = tokens

        ctype = CType.from_tokens(type)
        name = Identifier.from_tokens(identifier)

        (next_token, *_), *rest = rest
        match next_token:
            case "=":
                exp, rest = Expression.from_tokens(rest)
                return Variable_Declaration(
                    type=ctype,
                    name=name,
                    init=exp,
                ), _next_is_semicolon(rest)
            case "SEMICOLON":
                return Variable_Declaration(type=ctype, name=name, init=None), rest
            case _:
                raise ValueError("Syntax error!")


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
            res.append(pf.indent(f"(while {str(self.condition)}))"))

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
        if not tokens or len(tokens) == 1 and tokens[0][0] == "SEMICOLON":
            # Perfectly valid
            # for(; 1 ;) {...}
            return None
        decl = Variable_Declaration.from_tokens(tokens)
        if decl:
            actual_declaration, rest = decl
            assert rest == [], "We left food on the table!"
            return actual_declaration
        tokens_sans_semicolon = tokens[:-1]
        # If it's not a declaration it's _GOT_ to be an expression
        return Expression.from_tokens(tokens_sans_semicolon, assert_no_food_left=True)


class CType(RootModel[t.Literal["int"]]):
    # TODO(Joaquim): Get rid of this awfulness

    @staticmethod
    def from_tokens(token: lexer.Token_Lexed):
        assert token[0] == "INT_KEYWORD", "I know of no other CTypes! Sorry"
        return CType(token[1])  # pyright: ignore[reportArgumentType]


class ReturnStatement(BaseModel):
    exp: Expression

    @t.override
    def __str__(self):
        return f"(return {str(self.exp)})"


class IfStatement(BaseModel):
    condition: Expression
    then: Statement
    else_s: "Statement | None" = None

    @t.override
    def __str__(self):
        res = f"(if {str(self.condition)}\n"
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
        return f"(goto {str(self.label)})"


class Label(BaseModel):
    label: Identifier
    statement: Statement

    @t.override
    def __str__(self):
        return f"(label {str(self.label)}\n{pf.indent(str(self.statement))})"


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
            block_item = Variable_Declaration.from_tokens(tokens)
        with suppress(ValueError, AssertionError):
            block_item = Statement.from_tokens(tokens)
        with suppress(ValueError, AssertionError):
            block_item = Function_Declaration.from_tokens(tokens)
        if block_item is None:
            raise ValueError("I accept declarations or statements!")
        return block_item


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
        match self.type:
            case Factor(type=Constant(root=root)):
                return root
            # TODO: Stuff like `int a = 1;`
            # is valid if `a` is `const` or the compiler can tell
            # that no one else touched it
            # For now - imma just not care
            case _:
                raise ValueError("Not a const expression bro!")

    @staticmethod
    def from_constant(const: int):
        return Expression(type=Factor(type=Constant(const)))

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
        assert_no_food_left: t.Literal[False] = False,
        min_prec: int = 0,
    ) -> tuple[Expression, lexer.Lexed]: ...

    @t.overload
    @staticmethod
    def from_tokens(
        tokens: lexer.Lexed, assert_no_food_left: t.Literal[True], min_prec: int = 0
    ) -> Expression:
        """
        If we specify `assert_no_food_left` then we assert that the tokens we _would_ return are empty.
        """

    @staticmethod
    def from_tokens(
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

                operator = t.cast(Binary_Op_Or_Extras, operator)

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

    type: Constant | Unary | Expression | Identifier | FuncCall

    @t.override
    def __str__(self):
        match self.type:
            case Constant(root=root):
                return str(root)
            case _:
                return str(self.type)

    @staticmethod
    def parse(tokens: lexer.Lexed) -> tuple[Factor, lexer.Lexed]:
        (token, identifier, charno), *rest = tokens
        match token:
            case "IDENTIFIER":
                ident = Identifier.from_tokens((token, identifier, charno))
                if not rest or rest[0][0] != "OPEN_PARENS":
                    # It's just an identifier
                    return (
                        Factor(type=ident),
                        rest,
                    )

                _, *rest = rest
                corresponding_closed = get_closing(rest, ")")
                arg_list = FuncCall.args_from_tokens(rest[:corresponding_closed])

                return (
                    Factor(type=FuncCall(name=ident, args=arg_list)),
                    rest[corresponding_closed + 1 :],
                )
            case "CONSTANT":
                return (
                    Factor(
                        type=Constant(identifier),  # pyright: ignore[reportArgumentType]
                    ),
                    rest,
                )
            case "OPEN_PARENS":
                corresponding_closed = get_closing(rest, ")")
                return (
                    Factor(
                        type=Expression.from_tokens(
                            rest[:corresponding_closed], assert_no_food_left=True
                        )
                    ),
                    rest[corresponding_closed + 1 :],
                )

            case "COMPLEMENT" | "MINUS" | "NOT" | "++" | "--":
                exp, rest = Factor.parse(rest)
                return (
                    Factor(
                        type=Unary(type=token, exp=exp),
                    ),
                    rest,
                )
            case _:
                pass
        raise AssertionError(f"Syntax Error, unknown {token=} at {charno=}")


class FuncCall(BaseModel):
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
        return f"({str(self.type)} {str(self.exp)} {'' if self.pre else 'postfix'})"


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
        return f"({self.type} {str(self.lhs.type)} {str(self.rhs.type)})"


class NormalAssigment(BaseModel):
    lhs: LValue
    rhs: Expression

    @t.override
    def __str__(self):
        return f"(= {str(self.lhs)} {str(self.rhs.type)})"


class Conditional(BaseModel):
    left: Expression
    middle: Expression
    right: Expression

    @t.override
    def __str__(self):
        res = f"(if-expr {str(self.left)}\n"
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
        return f"({self.type} {str(self.lhs)} {str(self.rhs.type)})"


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
