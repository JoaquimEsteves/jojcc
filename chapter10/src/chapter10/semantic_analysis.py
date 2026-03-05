import typing as t
from contextlib import contextmanager, suppress
from contextvars import ContextVar

from pydantic import BaseModel, Field

import chapter10.parser as parser
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
        int foo = 1;
        {
            int foo = 2; // valid!
        }
        int foo = 2; // NOT VALID!

        ```

        ```c
        int foo(int bar, int baz); // Valid (has linkage)
        int foo(int wow, int valid); // Valid (who cares about warnings)
        ```
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

        match prev.has_linkage, decl.storage:
            case False, None:
                err = f"Redefinition of '{name}'"
            case False, "static":
                err = f"Redefinition of '{name}'. Old one is still in scope brother!"
            case False, "extern":
                err = f"Extern declaration of '{name}' follows non-extern declaration"
            case True, None:
                err = f"Non-extern declaration of '{name}' follows extern declaration"
            case True, "static":
                err = f"Static declaration of '{name}' follows non-static declaration"
            case True, "extern":
                # They refer to the same object
                err = None

        if err:
            raise AssertionError(err)

    def valid_function_declaration(self, func: parser.Function_Declaration):
        name = func.name.root
        if name not in self.data:
            return True
        prev = self.data[name]

        if not prev.from_current_scope():
            # perfectly fine (but weird)
            # Examples:
            # ```c
            # int printf = 5;
            # if (printf > 1) {
            #   int printf(const char *, ...);
            #   printf("it just works!\n")
            # }
            # ```
            #
            return True
        # If it's something that will be linked externally
        # So `int foo(void)` is valid! but `int foo; int foo(void)` is not!
        return prev.has_linkage

    def valid_func_call(self, name: str):
        if name not in self.data:
            return False
        return True

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
            data={key: val for (key, val) in self.data.items()},
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
        return self.data.get(name)

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
        type: tuple[parser.CType, tuple[parser.CType, ...]]

    class Static(BaseModel):
        initial_value: t.Literal["tentative", "Nope!"] | int
        type: parser.CType
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

    def valid_declaration(self, name: str):
        if name not in self.data:
            return True
        return False

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
                case parser.Label(label=label, statement=inner):
                    if label.root in found_labels:
                        raise ValueError(f"Label {item} declared multiple times!")
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
            raise ValueError(
                f"Missing some requested labels!\n{found_labels=}\n{requested_labels=}"
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
MOST_RECENT_CONTROL_LABEL: ContextVar[ContextVar[str] | None] = ContextVar(
    "MOST_RECENT ", default=None
)
"""
Where do those damn breaks apply to
"""
IS_TOP_LEVEL: ContextVar[bool] = ContextVar("IS_TOP_LEVEL", default=True)
SYMBOL_TABLE = ContextVar("SYMBOL_TABLE", default=Symbol_Table())
"""
The book mentions that the symbol-table is de-facto a global, but I still made
it a context-variable just to make testing a little easier.
"""


###############################################################################
#                                                                             #
#                                Resolve Funcs                                #
#                                                                             #
###############################################################################


def resolve_program(prog: parser.Program):
    def fix_functions(original: parser.Function_Declaration):
        # Important that the `LABEL_MAP` gets redefined _before_ `resolve_function_declaration`
        # As it's _that_ function that changes the names of all of the labels
        with pf.set_context(LABEL_MAP, Label_Map()):
            fixed = resolve_function_declaration(original)
            Label_Map.check_labels_in_function(fixed)
            if not fixed.body:
                return fixed

        if fixed.return_type.root == "int":
            # Ensures that there's always a return statement at the end
            # C-standard says that only `main` cares about this.
            # But the book says to do it for every function so whatever.
            fixed.body.body.append(
                parser.Statement(
                    root=parser.ReturnStatement(exp=parser.Expression.from_constant(0))
                )
            )
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

    # We denote a new scope, because `int a(int a);` is valid
    with Identifier_Table.new_scope():
        param_list = [resolve_declaration(param) for param in func.param_list]

        if func.body:
            assert IS_TOP_LEVEL.get(), "No clojures nerd!"
            # Note - that we're in the same scope.
            # int foo(int a) { int a = 2; }
            # is ILLEGAL
            with pf.set_context(IS_TOP_LEVEL, False):
                body = resolve_block(func.body)
        else:
            body = None

    return parser.Function_Declaration(
        return_type=func.return_type,
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
    return parser.Block(body=[resolve_block_item(block) for block in body.body])


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
            assert decl.storage is None, "No external/static in for loops nerd!"
            return decl
        case parser.Expression():
            return resolve_expression(for_init)


def resolve_declaration(decl: parser.Variable_Declaration):
    variable_map = IDENTIFIER_TABLE.get()
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
        # if variable_map.scope != 0 and decl.init is not None:
        #     raise ValueError(
        #         "Declaration of block scope identifier with linkage cannot have an initializer"
        #     )
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
    match stmt.root:
        case "nope":
            return stmt

        case parser.Break():
            if not (control_label := _get_control_label()):
                raise ValueError("No control label found!")
            return parser.Statement(root=parser.Break(control_label=control_label))
        case parser.Continue():
            if not (control_label := _get_control_label("loop")):
                raise ValueError("No control label found!")
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
            found_cases: dict[str, parser.SwitchCase] = {}
            switch_label = _get_new_name("switch_label")
            with (
                pf.set_context(SWITCH_CONTROL_LABEL, switch_label),
                pf.set_context(FOUND_CASES, found_cases),
                pf.set_context(MOST_RECENT_CONTROL_LABEL, SWITCH_CONTROL_LABEL),
            ):
                checker = resolve_expression(checker)
                body = resolve_statement(body)
            return parser.Statement(
                root=parser.Switch(
                    checker=checker,
                    body=body,
                    associated_cases=list(found_cases.values()),
                    control_label=switch_label,
                )
            )
        case parser.SwitchCase(type=type, body=body):
            if not (control_label := _get_control_label("switch")):
                raise ValueError("No control label found!")
            body = resolve_statement(body)
            # We have to make sure that these cases were not used already in the same context
            found_cases = FOUND_CASES.get()
            as_str = type.model_dump_json()
            assert as_str not in found_cases, "This case was already found!"
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
            found_cases[as_str] = resolved
            return parser.Statement(root=resolved)


def resolve_assignable(
    identifier: parser.Identifier | parser.Expression | parser.Factor,
):
    if isinstance(identifier, (parser.Expression, parser.Factor)):
        current = identifier
        # Solves situations like so:
        # ((((((2))))))
        #
        # Note: This SHOULD have been taken care of before we hit this spot
        # But just in case...
        while hasattr(current, "type") and not isinstance(current.type, str):  # pyright: ignore[reportAttributeAccessIssue, reportUnknownArgumentType, reportUnknownMemberType]
            current = current.type  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType, reportUnknownVariableType]
        if isinstance(current, parser.Unary):
            # Postfix and pre-fix operators being a PITA as usual
            # This is a valid assignable value `~a++`
            assert current.type not in ("++", "--")
            return parser.Expression(
                type=parser.Factor(
                    type=parser.Unary(
                        type=current.type,
                        exp=resolve_assignable(current.exp).type,  # pyright: ignore[reportArgumentType, reportUnknownArgumentType, reportUnknownMemberType]
                        pre=current.pre,
                    )
                )
            )
        assert isinstance(current, parser.Identifier), f"{current} is not assignable!"
        identifier = current

    return parser.Expression(
        type=parser.Factor(type=resolve_identifier(identifier, IDENTIFIER_TABLE.get()))
    )


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
            raise ValueError(f"Identifier {name} not found!")

    return parser.Identifier(root=resolved_name)


def resolve_factor(factor: parser.Factor) -> parser.Factor:
    match factor.type:
        case parser.Constant():
            return factor
        case parser.Expression():
            return parser.Factor(type=resolve_expression(factor.type))
        case parser.Identifier():
            return parser.Factor(type=resolve_assignable(factor.type))
        case parser.Unary(type=type, exp=exp, pre=pre):
            if type not in ("++", "--"):
                return parser.Factor(
                    type=parser.Unary(type=type, exp=resolve_factor(exp), pre=pre)
                )
            # assert the boy is an lvalue
            return parser.Factor(
                type=parser.Unary(
                    type=type,
                    exp=resolve_assignable(exp).type,  # pyright: ignore[reportArgumentType]
                    pre=pre,
                )
            )
        case parser.Func_Call(name=parser.Identifier(root=name), args=args):
            identifier_table = IDENTIFIER_TABLE.get()
            assert identifier_table.valid_func_call(name), "Undeclared function!"
            new_name: str = identifier_table[name]  # pyright: ignore[reportAssignmentType]
            return parser.Factor(
                type=parser.Func_Call(
                    name=parser.Identifier(new_name),
                    args=[resolve_expression(arg) for arg in args],
                )
            )


def resolve_expression(exp: parser.Expression) -> parser.Expression:
    match exp.type:
        case parser.Conditional(left=left, middle=middle, right=right):
            return parser.Expression(
                type=parser.Conditional(
                    left=resolve_expression(left),
                    middle=resolve_expression(middle),
                    right=resolve_expression(right),
                )
            )
        case parser.NormalAssigment(lhs=lhs, rhs=rhs):
            return parser.Expression(
                type=parser.NormalAssigment(
                    lhs=resolve_assignable(lhs),
                    rhs=resolve_expression(rhs),
                )
            )
        case parser.FancyAssignment(lhs=lhs, rhs=rhs, type=type):
            # Pyright needed some help here
            rhs: parser.Expression

            def get_bin_op(type: parser.Binary_Op_Without_Assignment):
                return parser.Expression(
                    type=parser.BinaryOp(
                        type=type,
                        lhs=parser.Expression(type=parser.Factor(type=lhs)),
                        rhs=rhs,
                    )
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

            return parser.Expression(
                type=parser.NormalAssigment(
                    lhs=resolve_assignable(lhs),
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
# int main(void) {
#    int foo = randnumber();
#    if (foo > 0) {
#        int foo(void); // VALID
#        return foo();
#    }
#    return foo;
# }
#
# int foo(int a) { // ERROR! Foo DECLARED DIFFERENTLY
#    return 8;
# }
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

    # For now - every function just returns an int and accepts ints
    # So the only thing that matters is how many ints there are
    # func_type = len(func.param_list)
    has_body = func.body is not None
    name = func.name.root

    if name not in symbol_table:
        already_defined = False
        is_global = func.storage != "static"
    else:
        # Shoot. Let's go through the checklist
        old = symbol_table.data[name]
        if not isinstance(old, Symbol_Table.Func):
            raise ValueError("This mfer is a variable yo")
        already_defined = old.defined

        if already_defined and has_body:
            raise ValueError("Tried to define a function twice!")

        if len(old.type[1]) != len(func.param_list):
            raise ValueError("Conflicting types bro!")

        if old.is_global and func.storage == "static":
            raise ValueError("Static function declaration follows non-static")

        is_global = old.is_global

    symbol_table.data[name] = Symbol_Table.Func(
        type=(parser.CType("int"), tuple(param.type for param in func.param_list)),
        defined=already_defined or has_body,
        is_global=is_global,
    )

    if not has_body:
        return

    body = func.body.body  # pyright: ignore[reportOptionalMemberAccess]

    for param in func.param_list:
        type_check_local_variable_declaration(param)
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

    match decl.storage:
        case "extern":
            if decl.init:
                raise ValueError("Initializer on local extern variable declaration!")
            if decl.name in symbol_table:
                old = symbol_table.data[decl.name.root]
                assert not isinstance(old, Symbol_Table.Func), (
                    f"Redefinition of '{decl.name.root}' as different kind of symbol. "
                    "Old one was a function, new one is an extern!"
                )
            else:
                symbol_table.data[decl.name.root] = Symbol_Table.Static(
                    initial_value="Nope!",
                    type=parser.CType("int"),
                    is_global=True,
                )

        case "static":
            initial_value = decl.init.get_const_expression() if decl.init else 0
            symbol_table.data[decl.name.root] = Symbol_Table.Static(
                initial_value=initial_value,
                type=parser.CType("int"),
                is_global=False,
            )
        case None:
            assert decl.name.root not in symbol_table, (
                "Compiler bug! The identifier map messed up brother"
            )
            symbol_table.data[decl.name.root] = Symbol_Table.Local(
                type=parser.CType("int")
            )

            if decl.init:
                type_check_expression(decl.init)


def type_check_file_scope_variable_declaration(decl: parser.Variable_Declaration):
    initial_value: t.Literal["tentative", "Nope!"] | int
    symbol_table = SYMBOL_TABLE.get()

    match decl.init, decl.storage:
        case None, "extern":
            initial_value = "Nope!"
        case None, _:
            initial_value = "tentative"
        case parser.Expression(), "extern":
            raise ValueError("This should have been caught earlier no?")
        case parser.Expression(), _:
            initial_value = decl.init.get_const_expression()

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
            case int(), int():
                raise ValueError(f"Conflict! Double declaration of '{decl.name.root}'")
            case int(), _:
                # perfectly valid...still jank
                initial_value = old.initial_value
            case "tentative", "Nope" | "tentative":
                initial_value = "tentative"
            case "Nope!", int() | "tentative" | "Nope!":
                # Valid
                # `extern int a;...int a = 3;`
                # We can redeclare it or assign it or whatever. Really weird
                pass
            case "tentative", "Nope!" | int():
                # Valid
                # `int a;extern int a; int a = 3;`
                pass

    symbol_table.data[decl.name.root] = Symbol_Table.Static(
        type=parser.CType("int"),
        initial_value=initial_value,
        is_global=is_global,
    )


def type_check_expression(exp: parser.Expression | parser.Factor):
    symbol_table = SYMBOL_TABLE.get()
    match exp.type:
        case parser.Identifier(root=name):
            type_check_identifier(exp.type)
        case parser.Func_Call(name=parser.Identifier(root=name), args=args):
            old = symbol_table.data[name]
            if not isinstance(old.type, tuple):
                raise ValueError("Type Error!")
            if len(old.type[1]) != len(args):
                raise ValueError("Incorrect number of arguments!")
        case parser.Factor() | parser.Expression():
            # Recursion...
            type_check_expression(exp.type)
        # Because they're all ints, for now we ain't gotta check shit

        case parser.BinaryOp(lhs=lhs, rhs=rhs):
            type_check_expression(lhs)
            type_check_expression(rhs)
        case parser.Unary(exp=exp):
            type_check_expression(exp)
        case parser.Conditional(left=left, middle=middle, right=right):
            for exp in (left, middle, right):
                type_check_expression(exp)
        case (
            parser.FancyAssignment(lhs=lhs, rhs=rhs)
            | parser.NormalAssigment(lhs=lhs, rhs=rhs)
        ):
            match lhs:
                case parser.Expression():
                    type_check_expression(lhs)
                case parser.Identifier():
                    type_check_identifier(lhs)
            type_check_expression(rhs)
        case parser.Constant():
            pass


def type_check_identifier(ident: parser.Identifier):
    name = ident.root
    old = SYMBOL_TABLE.get().data[name]
    if not isinstance(old.type, parser.CType):
        raise ValueError("Type Error!")


def type_check_statement(stmt: parser.Statement):
    match stmt.root:
        case parser.ReturnStatement(exp=exp):
            type_check_expression(exp)
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
            type_check_statement(body)
        case parser.SwitchCase(type=type, body=body):
            type_check_statement(body)
            match type:
                case parser.SwitchCase.Default():
                    pass
                case parser.SwitchCase.Case(check=check):
                    type_check_expression(check)
        case (
            "nope" | parser.Break() | parser.Continue() | parser.Goto() | parser.Label()
        ):
            pass


###############################################################################
#                                lil' helpers                                 #
###############################################################################


def _get_new_name(original: str):
    global Global_Counter
    # Note: We ensure that the new name is not valid-c
    # Otherwise the variables `int a, a1` could both be renamed to
    # `a12`
    new_name = f"{original}`{Global_Counter}"
    Global_Counter += 1
    return new_name


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
