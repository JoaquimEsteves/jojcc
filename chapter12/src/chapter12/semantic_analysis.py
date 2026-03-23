import typing as t
from contextlib import contextmanager, suppress
from contextvars import ContextVar

from pydantic import BaseModel, Field

import chapter12.parser as parser
import chapter12.lexer as lexer
from shared import pure_functions as pf

Global_Counter: int = 0
"""
Will be used during tacky as well.
This is to ensure that the tacky-boys don't somehow end up using the same
name as this one.
"""


class Identifier_Table(BaseModel):
    data: dict[str, Identifier] = {}
    scope: int = 0

    class Identifier(BaseModel):
        """
        Simply informs us if we can declare an item or not.
        Example:

        ```c
        int foo = 1; // scope = 0, renamed to `foo_0`
        {
            int foo = 2; // scope 1, renamed to `foo_1`
        }
        int foo = 2; // NOT VALID!
        ```

        ```c
        int foo(int bar, int baz); // Valid (has linkage)
        int foo(int wow, int valid); // Valid (We don't warn about the variables having a different name)
        ```

        Note: Type-checking is done later, using the `symbol-table`
        """

        name: str
        has_linkage: bool
        scope: int = Field(default_factory=lambda: IDENTIFIER_TABLE.get().scope)

        def from_current_scope(self) -> bool:
            return self.scope == IDENTIFIER_TABLE.get().scope

    def assert_valid_variable_declaration(self, decl: parser.Variable_Declaration):
        name = decl.name.root
        if name not in self.data:
            return
        prev = self.data[name]
        if not prev.from_current_scope():
            return

        err_name = _og(name)
        match prev.has_linkage, decl.storage:
            case False, None:
                err = f"Redefinition of '{err_name}'"
            case False, "static":
                err = (
                    f"Redefinition of '{err_name}'. Old one is still in scope brother!"
                )
            case False, "extern":
                err = (
                    f"Extern declaration of '{err_name}' follows non-extern declaration"
                )
            case True, None:
                err = (
                    f"Non-extern declaration of '{err_name}' follows extern declaration"
                )
            case True, "static":
                err = (
                    f"Static declaration of '{err_name}' follows non-static declaration"
                )
            case True, "extern":
                # They refer to the same object
                err = None

        if err:
            raise SemanticError(decl.location, err)

    def valid_function_declaration(self, func: parser.Function_Declaration):
        name = func.name.root
        if name not in self.data:
            return True
        prev = self.data[name]

        if not prev.from_current_scope():
            # perfectly fine (but weird)
            # Examples:
            # // ```c
            # // int printf = 5;
            # // if (printf > 1) {
            # //   int printf(const char *, ...);
            # //   printf("it just works!\n")
            # // }
            # // ```
            #
            return True
        # If it's something that will be linked externally
        # So `int foo(void)` is valid! but `int foo; int foo(void)` is not!
        return prev.has_linkage

    def valid_func_call(self, name: str):
        return name in self.data

    def __getitem__(self, name: str):
        entry = self.data.get(name)
        return entry.name if entry else None

    def __contains__(self, name: str | parser.Identifier):
        match name:
            case parser.Identifier(root=root):
                return root in self.data
            case _:
                return name in self.data

    def get_new_name(self, original: str):
        new_name = _get_new_name(original)
        self.data[original] = Identifier_Table.Identifier(
            name=new_name,
            has_linkage=False,
        )

        return new_name

    def add_external(self, decl: parser.Declaration):
        self.data[decl.name.root] = Identifier_Table.Identifier(
            name=decl.name.root,
            has_linkage=True,
        )

    def get_copy(self):
        return Identifier_Table(
            data=dict(self.data.items()),
            scope=self.scope + 1,
        )

    @staticmethod
    @contextmanager
    def new_scope():
        with pf.set_context(IDENTIFIER_TABLE, IDENTIFIER_TABLE.get().get_copy()):
            yield


class Symbol_Table(BaseModel):
    """
    The symbol-table is used for type-checking
    Note: DO NOT attempt to do type-checking as you're still going through the identifier map!
    (I wasted too long on that trying to do the whole thing in one pass...)
    Before identifier map:

    ```c
    int foo(int foo) {
        if (foo > 0) {
            int cpy = foo;
            int foo(int foo);
            return foo(cpy - 1);
        }
        return 0;
    }
    ```

    After:

    ```c
    int foo(int foo_0) { // every identifier has a different little string
                         // Much easier to type-check!
        if (foo_0 > 0) {
            int cpy_0 = foo;
            int foo(int foo_1);
            return foo(cpy_0 - 1);
        }
        return 0;
    }
    ```

    """

    data: dict[str, Symbol] = {}

    def is_external(self, name: str):
        match self.data[name]:
            case (
                Symbol_Table.Func(is_global=is_global)
                | Symbol_Table.Static(is_global=is_global)
            ):
                return is_global
            case Symbol_Table.Local():
                return False

    def assert_declaration_has_type_match(self, decl: parser.Variable_Declaration):
        old = self.data.get(decl.name.root)
        if old is None:
            return
        # If an old exists, it _must_ be a static-variable
        # (If it was a local then variable-declaration would be an invalid double-declaration)
        assert isinstance(old, Symbol_Table.Static)
        assert old.type.root == decl.type.root, (
            f"Types are different {old.type=} {decl.type=}"
        )

    def __contains__(self, name: str | parser.Identifier):
        match name:
            case parser.Identifier(root=root):
                return root in self.data
            case _:
                return name in self.data

    type Symbol = Func | Static | Local

    class Func(BaseModel):
        defined: bool
        is_global: bool
        type: parser.CType.FuncType

    class Static(BaseModel):
        class StaticInit(BaseModel):
            val: int

            @staticmethod
            def from_declaration(decl: parser.Variable_Declaration, *, mutate: bool):
                with pf.set_context(lexer.CURRENT_LOCATION, decl.location):
                    val = (
                        decl.init.get_const_expression(
                            cast_to=decl.type.get_trivial(), mutate=mutate
                        )
                        if decl.init
                        else 0
                    )
                    return Symbol_Table.Static.StaticInit(
                        val=val,
                    )

        initial_value: t.Literal["tentative", "Nope!"] | StaticInit
        type: parser.TrivialType
        is_global: bool

    class Local(BaseModel):
        type: parser.CType


class Label_Map(BaseModel):
    """
    Labels (unlike variable declarations) are quite simple.
    Labels are unique per function. Simple as

    We still do the shenanigans that switch their programmer given-name into
    our own.
    """

    data: dict[str, str] = {}

    OG_NAMES: t.ClassVar[dict[str, str]] = {}
    """
    Only used to print better error messages
    """

    def valid_declaration(self, name: str):
        return name not in self.data

    def __getitem__(self, name: str):
        return self.data.get(name)

    def get_new_name(self, original: str):
        new_name = _get_new_name(original)
        self.data[original] = new_name

        return new_name

    @staticmethod
    def check_labels_in_function(func: parser.Function_Declaration):
        """
            Checks for:
            * using the same label for two labeled statements in the same function

            ```c
            int foo() {
            goto INVALID_NOT_FOUND;
        valid_label:
        invalid_label_duplicated:
        invalid_label_duplicated:
            }

            int bar() {
        valid_label:
                printf("Same label but in a different scope!")
            }
            ```
        """
        if not func.body:
            # nothing to check
            return
        body = func.body.body

        found_labels: set[str] = set()
        requested_labels: set[str] = set()

        def match_stmt(stmt: parser.Block_Item):
            if not isinstance(stmt, parser.Statement):
                return
            match stmt.root:
                case parser.Break() | parser.Continue():
                    pass
                case (
                    parser.While(body=body)
                    | parser.DoWhile(body=body)
                    | parser.For(body=body)
                    | parser.Switch(body=body)
                    | parser.SwitchCase(body=body)
                ):
                    match_stmt(body)
                case parser.Block(body=body):
                    for b in body:
                        match_stmt(b)
                case parser.Goto(label=label):
                    requested_labels.add(label.root)
                case parser.Label(label=label, statement=inner, location=location):
                    if label.root in found_labels:
                        raise SemanticError(
                            location, f"Label {item} declared multiple times!"
                        )
                    found_labels.add(label.root)
                    match_stmt(inner)
                case parser.ReturnStatement() | parser.Expression() | "nope":
                    pass
                case parser.IfStatement(then=then, else_s=else_s):
                    match_stmt(then)
                    if else_s:
                        match_stmt(else_s)

        # Every function will have it's own label-map
        for item in body:
            match_stmt(item)

        if requested_labels - found_labels != set():
            raise SemanticError(
                func.location,
                f"Missing some requested labels!\n{found_labels=}\n{requested_labels=}",
            )


###############################################################################
#                                                                             #
#                                Context Vars                                 #
#                                                                             #
###############################################################################
# They're globals with a cute little bow on top.
# The advantage is that using the `set_context` function
# we can have them be scoped trivially without a *BUNCH* of prop-drilling.
IDENTIFIER_TABLE = ContextVar("IDENTIFIER_TABLE ", default=Identifier_Table())
LABEL_MAP = ContextVar("LABEL_MAP ", default=Label_Map())
SWITCH_CONTROL_LABEL = ContextVar("SWITCH_CONTROL_LABEL ", default="")
LOOP_CONTROL_LABEL = ContextVar("LOOP_CONTROL_LABEL ", default="")
FOUND_CASES: ContextVar[dict[str, parser.SwitchCase]] = ContextVar(
    "FOUND_CASES", default={}
)
"""
cases can't be repeated inside a switch!
"""
TYPE_OF_SWITCH: ContextVar[parser.TrivialType | None] = ContextVar(
    "TYPE_OF_SWITCH", default=None
)
"""
A `case` must be converted to the type of the switch.
"""
MOST_RECENT_CONTROL_LABEL: ContextVar[ContextVar[str] | None] = ContextVar(
    "MOST_RECENT ", default=None
)
"""
Where do those damn breaks apply to
"""
SYMBOL_TABLE = ContextVar("SYMBOL_TABLE", default=Symbol_Table())
"""
The book mentions that the symbol-table is de-facto a global, but I still made
it a context-variable just to make testing a little easier.
"""
CURRENT_FUNCTION: ContextVar[parser.Function_Declaration | None] = ContextVar(
    "CURRENT_FUNCTION", default=None
)


###############################################################################
#                                                                             #
#                                Resolve Funcs                                #
#                                                                             #
###############################################################################


def resolve_program(prog: parser.Program):
    """
    TODO(Joaquim): This function is IMPURE!

    We _should_ enforce purity, the issue comes from the type-checkers needing to modify
    the state.
    """

    def fix_functions(original: parser.Function_Declaration):
        _ = lexer.CURRENT_LOCATION.set(original.location)
        # Important that the `LABEL_MAP` gets redefined _before_ `resolve_function_declaration`
        # As it's _that_ function that changes the names of all of the labels
        with pf.set_context(LABEL_MAP, Label_Map()):
            fixed = resolve_function_declaration(original)
            Label_Map.check_labels_in_function(fixed)
            if not fixed.body:
                return fixed

        # From the book:
        # > In Chapter 5, I mentioned that we add an extra Return instruction
        # > to the end of each TACKY function, in case not every execution path
        # > in the original C function reaches a return statement. This extra
        # > instruction can always return ConstInt(0), even when the function's
        # > return type isn't int. When we return from main, this is the correct
        # > return type. When we return from any other function that's missing an
        # > explicit return statement, the return value is undefined. We still
        # > need to return control to the caller, but we aren't obligated to
        # > return any particular value, so it doesn't matter if we get the type
        # > wrong.

        return_zero = parser.Statement(
            root=parser.ReturnStatement(
                exp=parser.Expression.from_constant(
                    0,
                    parser.CType(root="int"),
                )
            )
        )

        match fixed.body.body and fixed.body.body[-1]:
            case parser.Statement(root=parser.ReturnStatement()):
                pass
            case _:
                # Ensures that there's always a return statement at the end
                # C-standard says that only `main` cares about this.
                # But the book says to do it for every function so whatever.
                fixed.body.body.append(return_zero)
        return fixed

    fixed: list[parser.Declaration] = []
    for decl in prog.declarations:
        match decl:
            case parser.Function_Declaration():
                tweaked = fix_functions(decl)
            case parser.Variable_Declaration():
                tweaked = resolve_declaration(decl)
        fixed.append(tweaked)

    # We have to type-check AFTER
    for decl in fixed:
        match decl:
            case parser.Function_Declaration():
                type_check_function(decl)
            case parser.Variable_Declaration():
                type_check_file_scope_variable_declaration(decl)

    return parser.Program(declarations=fixed)


def resolve_function_declaration(func: parser.Function_Declaration):
    id_table = IDENTIFIER_TABLE.get()
    assert id_table.valid_function_declaration(func)
    id_table.add_external(func)

    _ = lexer.CURRENT_LOCATION.set(func.location)
    is_top_level = id_table.scope == 0

    # We denote a new scope, because `int a(int a);` is valid
    with Identifier_Table.new_scope():
        param_list = [
            resolve_declaration(
                parser.Variable_Declaration(
                    type=func.type.params[index],
                    name=param,
                    init=None,
                    storage=None,
                )
            ).name
            for index, param in enumerate(func.param_list)
        ]

        if func.body:
            if not is_top_level:
                raise SemanticError(func.location, "No clojures nerd!")
            # Note - that we're in the same scope.
            # int foo(int a) { int a = 2; }
            # is ILLEGAL
            # with pf.set_context(IS_TOP_LEVEL, val=False):
            body = resolve_block(func.body)
        else:
            body = None

    return parser.Function_Declaration(
        type=func.type,
        name=func.name,
        param_list=param_list,
        body=body,
        storage=func.storage,
    )


def resolve_block(body: parser.Block) -> parser.Block:
    """
    Note: A new block does not necessarily mean a new scope.
    Example-Error: `int _(int foo) { int foo; }` is an error!
    """
    return parser.Block(
        body=[resolve_block_item(block) for block in body.body], location=body.location
    )


def resolve_block_item(block: parser.Block_Item):
    match block:
        case parser.Variable_Declaration():
            return resolve_declaration(block)
        case parser.Statement():
            return resolve_statement(block)
        case parser.Function_Declaration():
            func = resolve_function_declaration(block)
            assert func.storage != "static", (
                "Can't have static function declarations inside a block!"
            )
            return func


def resolve_for_init(for_init: parser.For_Init) -> parser.For_Init:
    match for_init:
        case None:
            return None
        case parser.Variable_Declaration():
            decl = resolve_declaration(for_init)
            if decl.storage is not None:
                raise SemanticError(
                    for_init.location, "No external/static in for loops nerd!"
                )
            return decl
        case parser.Expression():
            return resolve_expression(for_init)


def resolve_declaration(decl: parser.Variable_Declaration):
    variable_map = IDENTIFIER_TABLE.get()
    _ = lexer.CURRENT_LOCATION.set(decl.location)
    if variable_map.scope == 0:
        # SPECIAL RULES!
        # We don't validate at all (yet), we treat them as external and move on.
        # These guys will later on be type-checked
        # I think the rules are "relaxed" so that users could invoke `gcc` like so:
        # `gcc folder_with_lots_of_c/**/*.c`
        # Or because of historical `<#include>` shenanigans
        variable_map.add_external(decl)
        return decl

    variable_map.assert_valid_variable_declaration(decl)

    if decl.storage == "extern":
        variable_map.add_external(decl)
        # According to the book we do this in the type-checking phase
        # // if variable_map.scope != 0 and decl.init is not None:
        # //     raise ValueError(
        # //         "Declaration of block scope identifier with linkage cannot have an initializer"
        # //     )
        return decl

    old_name = decl.name.root
    new_name = variable_map.get_new_name(old_name)
    new_id = parser.Identifier(new_name)

    if decl.init is None:
        return parser.Variable_Declaration(
            type=decl.type, name=new_id, init=None, storage=decl.storage
        )

    new_exp = resolve_expression(decl.init)

    return parser.Variable_Declaration(
        type=decl.type, name=new_id, init=new_exp, storage=decl.storage
    )


def resolve_statement(stmt: parser.Statement) -> parser.Statement:
    loc = stmt.location
    _ = lexer.CURRENT_LOCATION.set(stmt.location)
    match stmt.root:
        case "nope":
            return stmt

        case parser.Break():
            if not (control_label := _get_control_label()):
                raise SemanticError(stmt.location, "No control label found!")
            return parser.Statement(
                root=parser.Break(control_label=control_label, location=loc),
                location=loc,
            )
        case parser.Continue():
            if not (control_label := _get_control_label("loop")):
                raise SemanticError(stmt.location, "No control label found!")
            return parser.Statement(root=parser.Continue(control_label=control_label))
        case parser.For(init=init, condition=condition, post=post, body=body):
            with (
                Identifier_Table.new_scope(),
                pf.set_context(LOOP_CONTROL_LABEL, _get_new_name("for_label")),
                pf.set_context(MOST_RECENT_CONTROL_LABEL, LOOP_CONTROL_LABEL),
            ):
                init = resolve_for_init(init)
                condition = resolve_expression(condition) if condition else None
                post = resolve_expression(post) if post else None
                body = resolve_statement(body)
                return parser.Statement(
                    root=parser.For(
                        init=init,
                        condition=condition,
                        post=post,
                        body=body,
                        control_label=LOOP_CONTROL_LABEL.get(),
                    )
                )
        case (
            parser.DoWhile(condition=condition, body=body)
            | parser.While(condition=condition, body=body)
        ):
            with (
                Identifier_Table.new_scope(),
                pf.set_context(LOOP_CONTROL_LABEL, _get_new_name("while_label")),
                pf.set_context(MOST_RECENT_CONTROL_LABEL, LOOP_CONTROL_LABEL),
            ):
                condition = resolve_expression(condition)
                body = resolve_statement(body)
                cls = stmt.root.__class__
                return parser.Statement(
                    root=cls(
                        body=body,
                        condition=condition,
                        control_label=LOOP_CONTROL_LABEL.get(),
                    )
                )
        case parser.Block():
            with Identifier_Table.new_scope():
                return parser.Statement(root=resolve_block(stmt.root))

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

        case parser.Goto(label=label):
            return parser.Statement(root=parser.Goto(label=resolve_goto_label(label)))

        case parser.Label(label=label, statement=statement):
            return parser.Statement(
                root=parser.Label(
                    label=resolve_goto_label(label),
                    statement=resolve_statement(statement),
                )
            )

        case parser.Switch(checker=checker, body=body):
            switch_label = _get_new_name("switch_label")
            with (
                pf.set_context(SWITCH_CONTROL_LABEL, switch_label),
                pf.set_context(MOST_RECENT_CONTROL_LABEL, SWITCH_CONTROL_LABEL),
            ):
                checker = resolve_expression(checker)
                body = resolve_statement(body)
            return parser.Statement(
                root=parser.Switch(
                    checker=checker,
                    body=body,
                    # Note: We populate this field ONLY on the `type-checking` phase
                    # It's just easiest that way
                    associated_cases=[],
                    control_label=switch_label,
                )
            )
        case parser.SwitchCase(type=type, body=body):
            if not (control_label := _get_control_label("switch")):
                raise SemanticError(stmt.location, "No control label found!")
            # Note: That we check that all of the cases are correct in the type-check phase
            # We have to coerce the switch-cases into a `const-expression` anyway,
            # this const-expression coersion is best done on the type-checker
            body = resolve_statement(body)
            match type:
                case parser.SwitchCase.Case(check=check):
                    assert check.is_const_expression(), "Not a constant expression bro!"
                    type = parser.SwitchCase.Case(check=resolve_expression(check))
                case parser.SwitchCase.Default():
                    pass
            resolved = parser.SwitchCase(
                type=type,
                body=body,
                control_label=control_label,
                label=parser.Identifier(_get_new_name("case")),
            )
            return parser.Statement(root=resolved)


def resolve_valid_lvalue(lvalue: parser.LValue) -> parser.LValue:
    _ = lexer.CURRENT_LOCATION.set(lvalue.location)
    match lvalue:
        case parser.Expression():
            # shit...
            match lvalue.root:
                case parser.Identifier():
                    identifier: parser.Identifier = lvalue.root
                    return parser.Expression(
                        type=None,
                        root=resolve_identifier(identifier, IDENTIFIER_TABLE.get()),
                    )

                case parser.Normal_Assignment(lhs=lhs, rhs=rhs):
                    return parser.Expression(
                        type=None,
                        root=parser.Normal_Assignment(
                            # The LHS _must_ be an identifier or something
                            # that resolves to an identifier
                            lhs=resolve_valid_lvalue(lhs),
                            rhs=resolve_expression(rhs),
                        ),
                    )
                case _:
                    raise SemanticError(
                        lvalue.location,
                        f"This {lvalue} does not look like an lvalue to me!",
                    )


def resolve_post_and_prefix_assignable(
    exp: parser.Expression,
) -> parser.Expression:
    """
    Everyone knows what an lvalue is right?
    But C also has this `not assignable`...idea

    I still DON'T know what is something that is not assignable
    I just know, that `++a++` is NOT assignable
    """
    current = exp.root
    match current:
        case parser.Unary(op=op, exp=inner, pre=pre):
            # Postfix and pre-fix operators being a PITA as usual
            # This is a valid assignable value `~a++`
            assert op not in ("++", "--")

            return parser.Expression(
                type=None,
                root=parser.Unary(
                    op=op,
                    exp=resolve_post_and_prefix_assignable(inner),
                    pre=pre,
                ),
            )
        case parser.Identifier():
            return parser.Expression(
                type=None,
                root=resolve_identifier(current, IDENTIFIER_TABLE.get()),
            )
        case _:
            raise SemanticError(exp.location, f"{current} is not assignable!")


def resolve_goto_label(label: parser.Identifier):
    return resolve_identifier(
        label,
        where_to_check=LABEL_MAP.get(),
    )


def resolve_identifier(
    identifier: parser.Identifier,
    where_to_check: Label_Map | Identifier_Table,
):
    """
    In some cases - it's ok for our name to not be declared
    """
    name = identifier.root

    resolved_name = where_to_check[name]

    if resolved_name is None:
        # Labels can be defined later
        if isinstance(where_to_check, Label_Map):
            resolved_name = where_to_check.get_new_name(name)
        else:
            raise SemanticError(
                identifier.location, f"Identifier {_og(name)} not found!"
            )

    return parser.Identifier(root=resolved_name)


def resolve_factor(
    factor: parser.Expression.FactorSubType,
) -> parser.Expression.FactorSubType:
    _ = lexer.CURRENT_LOCATION.set(factor.location)
    match factor:
        case parser.Cast(target_type=target_type, exp=exp):
            # It feels really weird that we're checking here
            # I think I messed up my operator precedence somewhere
            assert not isinstance(
                exp.root, (parser.Normal_Assignment, parser.Fancy_Assignment)
            ), "LValue bullshit"
            return parser.Cast(target_type=target_type, exp=resolve_expression(exp))

        case parser.Constant():
            return factor
        case parser.Identifier():
            return resolve_identifier(factor, IDENTIFIER_TABLE.get())
        case parser.Unary(op=op, exp=exp, pre=pre):
            if op not in ("++", "--"):
                inner = resolve_expression(exp)
                return parser.Unary(
                    op=op,
                    exp=inner,
                    pre=pre,
                )
            return parser.Unary(
                op=op,
                exp=resolve_post_and_prefix_assignable(exp),
                pre=pre,
            )
        case parser.Func_Call(name=parser.Identifier(root=name), args=args):
            identifier_table = IDENTIFIER_TABLE.get()
            assert identifier_table.valid_func_call(name), "Undeclared function!"
            new_name: str = identifier_table[name]  # pyright: ignore[reportAssignmentType]
            return parser.Func_Call(
                name=parser.Identifier(new_name),
                args=[resolve_expression(arg) for arg in args],
            )


def resolve_expression(exp: parser.Expression) -> parser.Expression:
    _ = lexer.CURRENT_LOCATION.set(exp.location)
    match exp.root:
        case parser.Conditional(left=left, middle=middle, right=right):
            return parser.Expression(
                type=None,
                root=parser.Conditional(
                    left=resolve_expression(left),
                    middle=resolve_expression(middle),
                    right=resolve_expression(right),
                ),
            )
        case parser.Normal_Assignment(lhs=lhs, rhs=rhs):
            return parser.Expression(
                type=None,
                root=parser.Normal_Assignment(
                    lhs=resolve_valid_lvalue(lhs),
                    rhs=resolve_expression(rhs),
                ),
            )
        case parser.Fancy_Assignment():
            return resolve_expression(
                parser.Expression(root=exp.root.to_normal_assignment(), type=None)
            )

        case parser.BinaryOp(lhs=lhs, rhs=rhs, op=op):
            return parser.Expression(
                type=None,
                root=parser.BinaryOp(
                    op=op,
                    lhs=resolve_expression(lhs),
                    rhs=resolve_expression(rhs),
                ),
            )
        case _:
            return parser.Expression(type=None, root=resolve_factor(exp.root))


###############################################################################
#                                                                             #
#                                Type Checkers                                #
#                                                                             #
###############################################################################
# Note: I really dislike this.
# I spent a long time trying to to the type-checking as we're resolving the `parser` stuff
# Sadly - that did *NOT* work out because of the following bullshit:
#
# ```
# //int main(void) {
# //   int foo = randnumber();
# //   if (foo > 0) {
# //       int foo(void); // VALID
# //       return foo();
# //   }
# //   return foo;
# //}
#
# //int foo(int a) { // ERROR! Foo DECLARED DIFFERENTLY
# //   return 8;
# //}
# ```
#
# If I try to `keep_relevant` on the identifier-table, then we'll get an error!
# Ideally - what I want is to have some global `STUFF_TO_TYPE_CHECK` list, and
# then as we resolve stuff we just append to that list, and then go through it
# in order. I dunno - this approach came about after mucho frustration. At this
# stage I just wanted to do it as the book wanted it to be done.
#
# Improvements: Add methods to append to the `STUFF_TO_TYPE_CHECK` directly to the
# `resolve` functions


def type_check_function(func: parser.Function_Declaration):
    symbol_table = SYMBOL_TABLE.get()

    has_body = func.body is not None
    name = func.name.root

    def nope(s: str):
        return SemanticError(func.location, s)

    if name not in symbol_table:
        already_defined = False
        is_global = func.storage != "static"
    else:
        # Shoot. Let's go through the checklist
        old = symbol_table.data[name]
        if not isinstance(old, Symbol_Table.Func):
            raise nope("This mfer is a variable yo")

        already_defined = old.defined

        if already_defined and has_body:
            raise nope("function twice!")

        if old.type.return_type != func.type.return_type:
            raise nope("Conflicting types bro!")
        if old.type.params != func.type.params:
            raise nope("Conflicting types bro!")
        if old.is_global and func.storage == "static":
            raise nope("Static function declaration follows non-static")

        is_global = old.is_global

    symbol_table.data[name] = Symbol_Table.Func(
        type=func.type,
        defined=already_defined or has_body,
        is_global=is_global,
    )

    if not has_body:
        return

    body = func.body.body  # pyright: ignore[reportOptionalMemberAccess]

    with pf.set_context(CURRENT_FUNCTION, func):
        for index, param in enumerate(func.param_list):
            decl = parser.Variable_Declaration(
                type=func.type.params[index],
                name=param,
                init=None,
                storage=None,
            )
            type_check_local_variable_declaration(decl)
        for item in body:
            type_check_block_item(item)


def type_check_block_item(item: parser.Block_Item):
    match item:
        case parser.Variable_Declaration():
            type_check_local_variable_declaration(item)
        case parser.Function_Declaration():
            type_check_function(item)
        case parser.Statement():
            type_check_statement(item)


def type_check_local_variable_declaration(decl: parser.Variable_Declaration):
    symbol_table = SYMBOL_TABLE.get()

    def nope(s: str):
        return SemanticError(decl.location, s)

    match decl.storage:
        case "extern":
            if decl.init:
                raise nope("Initializer on local extern variable declaration!")
            symbol_table.assert_declaration_has_type_match(decl)
            if decl.name not in symbol_table:
                symbol_table.data[decl.name.root] = Symbol_Table.Static(
                    initial_value="Nope!",
                    type=decl.type,
                    is_global=True,
                )

        case "static":
            initial_value = Symbol_Table.Static.StaticInit.from_declaration(
                decl, mutate=False
            )

            symbol_table.assert_declaration_has_type_match(decl)

            symbol_table.data[decl.name.root] = Symbol_Table.Static(
                initial_value=initial_value,
                type=decl.type,
                is_global=False,
            )

        case None:
            if decl.name.root in symbol_table:
                raise nope("Compiler bug! The identifier map messed up brother")
            symbol_table.data[decl.name.root] = Symbol_Table.Local(type=decl.type)

            if decl.init:
                type_check_expression(decl.init)


def type_check_file_scope_variable_declaration(decl: parser.Variable_Declaration):
    initial_value: t.Literal["tentative", "Nope!"] | Symbol_Table.Static.StaticInit
    symbol_table = SYMBOL_TABLE.get()

    def nope(s: str):
        return SemanticError(decl.location, s)

    match decl.init, decl.storage:
        case None, "extern":
            initial_value = "Nope!"
        case None, _:
            initial_value = "tentative"
        case parser.Expression(), "extern":
            raise nope("This should have been caught earlier no?")
        case parser.Expression(), _:
            initial_value = Symbol_Table.Static.StaticInit.from_declaration(
                decl, mutate=True
            )

    is_global = decl.storage != "static"

    if decl.name in symbol_table:
        # Run through the checklist
        old = symbol_table.data[decl.name.root]
        assert not isinstance(old, Symbol_Table.Func), (
            f"Redefinition of '{decl.name.root}' as different kind of symbol. "
            "Old one was a function, new one is a variable!"
        )

        assert not isinstance(old, Symbol_Table.Local), (
            f"Wait - how is '{decl.name.root}' already declared as a local???."
        )

        symbol_table.assert_declaration_has_type_match(decl)

        if decl.storage == "extern":
            # C-STANDARD JANK ALERT
            # Valid `static int a = 2; extern a`
            # So is `int a = 2; extern a`
            is_global = old.is_global
            # in both cases, `a` won't be a global symbol
        else:
            assert old.is_global == is_global, (
                f"Conflicting variable linkage! '{decl.name.root}' {is_global=} and yet {old.is_global=}."
            )

        # JANK ALERT
        match old.initial_value, initial_value:
            case Symbol_Table.Static.StaticInit(), Symbol_Table.Static.StaticInit():
                raise nope(f"Conflict! Double declaration of '{decl.name.root}'")
            case Symbol_Table.Static.StaticInit(), _:
                # perfectly valid...still jank
                initial_value = old.initial_value
            case "tentative", "Nope" | "tentative":
                initial_value = "tentative"
            case "Nope!", Symbol_Table.Static.StaticInit() | "tentative" | "Nope!":
                # Valid
                # `extern int a;...int a = 3;`
                # We can redeclare it or assign it or whatever. Really weird
                pass
            case "tentative", "Nope!" | Symbol_Table.Static.StaticInit():
                # Valid
                # `int a;extern int a; int a = 3;`
                pass

    symbol_table.data[decl.name.root] = Symbol_Table.Static(
        type=decl.type,
        initial_value=initial_value,
        is_global=is_global,
    )


def type_check_expression(exp: parser.Expression):
    symbol_table = SYMBOL_TABLE.get()

    def nope(s: str):
        return SemanticError(exp.location, s)

    match exp.root:
        case parser.Identifier(root=name):
            exp_type = type_check_identifier_is_not_function(exp.root)
            exp.type = exp_type
        case parser.Func_Call(name=parser.Identifier(root=name), args=args):
            old = symbol_table.data[name]
            if not isinstance(old.type, parser.CType.FuncType):
                raise nope(f"{_og(name)} is not a function!")
            new_args: list[parser.Expression] = []
            assert len(old.type.params) == len(args), "Wrong number of arguments bro!"
            for param, current_arg in zip(old.type.params, args, strict=True):
                type_check_expression(current_arg)
                if param != current_arg.type:
                    current_arg = _convert_to(current_arg, param)
                new_args.append(current_arg)
            exp.type = old.type.return_type
            exp.root.args = new_args

        case parser.BinaryOp(lhs=lhs, rhs=rhs, op=op):
            type_check_expression(lhs)
            type_check_expression(rhs)
            if op in ("AND", "OR"):
                # 1 and 0 are always ints in C
                exp.type = parser.CType.from_trivial("int")
                return
            if op in ("LEFT_SHIFT", "RIGHT_SHIFT"):
                new_rhs = _convert_to(rhs, parser.CType.from_trivial("int"))
                type_check_expression(new_rhs)
            else:
                common = _get_common_type(lhs.type, rhs.type)
                new_lhs = _convert_to(lhs, common)
                new_rhs = _convert_to(rhs, common)
                for tweaked in (new_lhs, new_rhs):
                    type_check_expression(tweaked)
                exp.root.lhs = new_lhs
                exp.root.rhs = new_rhs

            match op:
                case (
                    "PLUS"
                    | "MINUS"
                    | "ASTERISK"
                    | "FORWARD_SLASH"
                    | "PERCENT"
                    | "LEFT_SHIFT"
                    | "RIGHT_SHIFT"
                    | "AMPERSAND"
                    | "PIPE"
                    | "CARRET"
                ):
                    exp.type = exp.root.lhs.type
                case "LE" | "LT" | "GT" | "GE" | "==" | "!=":
                    exp.type = parser.CType(root="int")

        case parser.Unary(op=op, exp=inner):
            type_check_expression(inner)
            if op == "NOT":
                exp.type = parser.CType(root="int")
            exp.type = inner.type
        case parser.Conditional(left=left, middle=middle, right=right):
            for sub in (left, middle, right):
                type_check_expression(sub)
            assert middle.type and right.type, "Dude - where my types at?"
            exp.type = _get_common_type(middle.type, right.type)

        case (
            parser.Fancy_Assignment(lhs=lhs, rhs=rhs)
            | parser.Normal_Assignment(lhs=lhs, rhs=rhs)
        ):
            type_check_expression(lhs)
            typed_left = lhs.type
            type_check_expression(rhs)
            new_rhs = _convert_to(rhs, typed_left)
            if new_rhs != rhs:
                type_check_expression(new_rhs)
            exp.root.rhs = new_rhs
            exp.type = typed_left
        case parser.Constant(ctype=trivial_type):
            exp.type = trivial_type
        case parser.Cast(target_type=target_type, exp=inner):
            type_check_expression(inner)
            exp.type = target_type

    if exp.type is None:
        raise nope("exp should have a type at this stage!")


def type_check_identifier_is_not_function(
    ident: parser.Identifier,
) -> parser.TrivialType:
    """
    Ensures we're not invoking a function as a value
    (Shit _will_ get messy when we allow function pointers lol)
    """
    name = ident.root
    old = SYMBOL_TABLE.get().data[name]
    return parser.CType.assert_is_trivial(old.type)


def type_check_statement(stmt: parser.Statement):
    match stmt.root:
        case parser.ReturnStatement(exp=exp):
            current_func = CURRENT_FUNCTION.get()
            assert current_func, "Return called outside function nerd!"
            type_check_expression(exp)
            stmt.root.exp = _convert_to(exp, current_func.type.return_type)
        case parser.Expression():
            type_check_expression(stmt.root)
        case (
            parser.DoWhile(condition=condition, body=body)
            | parser.While(condition=condition, body=body)
        ):
            type_check_expression(condition)
            type_check_statement(body)
        case parser.For(
            init=init,
            condition=condition,
            post=post,
            body=body,
        ):
            match init:
                case None:
                    pass
                case parser.Variable_Declaration():
                    type_check_local_variable_declaration(init)
                case parser.Expression():
                    type_check_expression(init)
            if condition:
                type_check_expression(condition)
            if post:
                type_check_expression(post)
            type_check_statement(body)
        case parser.IfStatement(condition=condition, then=then, else_s=else_s):
            type_check_expression(condition)
            type_check_statement(then)
            if else_s:
                type_check_statement(else_s)
        case parser.Block(body=body):
            for b in body:
                type_check_block_item(b)
        case parser.Switch(checker=checker, body=body):
            type_check_expression(checker)
            trivial_type = parser.CType.assert_is_trivial(checker.type)

            found_cases: dict[str, parser.SwitchCase] = {}
            with (
                pf.set_context(TYPE_OF_SWITCH, trivial_type),
                pf.set_context(FOUND_CASES, found_cases),
            ):
                type_check_statement(body)
            # Finally - we can now add the cases!
            stmt.root.associated_cases = list(found_cases.values())
        case parser.SwitchCase(type=type, body=body, location=loc):
            cast_to = TYPE_OF_SWITCH.get()
            assert cast_to, "could not determine type of cast!"
            found_cases = FOUND_CASES.get()

            type_check_statement(body)

            match type:
                case parser.SwitchCase.Default():
                    as_str = "default"
                case parser.SwitchCase.Case():
                    as_str = str(
                        type.check.get_const_expression(
                            cast_to=cast_to.root,  # pyright: ignore[reportArgumentType]
                            mutate=True,
                        )
                    )

            if as_str in found_cases:
                raise SemanticError(loc, "This case was already found!")
            found_cases[as_str] = stmt.root

        case parser.Label(statement=statement):
            type_check_statement(statement)
        case "nope" | parser.Break() | parser.Continue() | parser.Goto():
            pass


class SemanticError(parser.ParseError): ...


###############################################################################
#                                lil' helpers                                 #
###############################################################################


def _convert_to(exp: parser.Expression, type: parser.CType | None):
    assert type
    if exp.type == type:
        return exp
    return parser.Expression(root=parser.Cast(target_type=type, exp=exp), type=type)


def _get_common_type(left: parser.CType | None, right: parser.CType | None):
    """
    C works off of a `rank` based system.

    Unsigned numbers have a higher rank than signed ones.
    Then we go by size, bigger size means bigger rank.
    """
    assert left and right and isinstance(left.root, str) and isinstance(right.root, str)

    if left == right:
        return left

    l_size, r_size = left.get_size(), right.get_size()

    if l_size == r_size:
        if left.root in ("int", "long"):
            return right
        return left

    if l_size > r_size:
        return left
    return right


def _get_new_name(original: str):
    global Global_Counter
    # Note: We ensure that the new name is not valid-c
    # Otherwise the variables `int a, a1` could both be renamed to
    # `a12`
    new_name = f"{original}`{Global_Counter}"
    Global_Counter += 1
    Label_Map.OG_NAMES[new_name] = original
    return new_name


def _og(new_name: str):
    return Label_Map.OG_NAMES.get(new_name, new_name)


def _get_control_label(type: t.Literal["all", "loop", "switch"] = "all"):
    match type:
        case "all":
            with suppress(AttributeError):
                return MOST_RECENT_CONTROL_LABEL.get().get()  # pyright: ignore[reportOptionalMemberAccess]
            return None
        case "loop":
            return LOOP_CONTROL_LABEL.get() or None
        case "switch":
            return SWITCH_CONTROL_LABEL.get() or None
