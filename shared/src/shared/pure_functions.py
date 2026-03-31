from collections.abc import Sequence, Iterator, Iterable
from contextvars import ContextVar
from inspect import Traceback
import re
import typing as t
import textwrap

from contextlib import AbstractContextManager, contextmanager, suppress
import shared.data_types as dt


def get_literal_vals[T](alias: T) -> frozenset[T]:
    """
    Stolen (and adapted) from: https://stackoverflow.com/a/78822523

    Yields a set that contains the values of some `t.Literal`

    Example:

    ```
    >>> type foo = Literal['hello', 'world']
    >>> get_literal_vals(foo)
    frozenset({'hello', 'world'})
    >>> get_literal_vals(Literal['hello', 'world'])
    frozenset({'hello', 'world'})
    >>> type DT = foo | Literal['hello', 'bar']
    >>> get_literal_vals(DT)
    frozenset({'hello', 'world', 'bar'})
    ```
    """

    def resolve(alias: t.TypeAliasType | tuple[T, ...] | T) -> Iterator[T]:
        match alias:
            case t.TypeAliasType():
                for val in resolve(t.get_args(alias.__value__)):  # pyright: ignore[reportAny]
                    yield from resolve(val)
                return
            case tuple():
                t_seq = t.cast(Sequence[T], alias)
                for element in t_seq:
                    yield from resolve(element)
                return
            case _:
                # Presume it's a `t.Literal`
                yield from resolve(t.get_args(alias))

        # Avoids yielding `t.Literal` again
        if not hasattr(alias, "__args__"):
            yield alias

    return frozenset(tuple(resolve(alias)))


def try_call[T](func: t.Callable[[], T], *exceptions: type[BaseException]):
    """
    Make exceptions STFU
    """
    with suppress(*exceptions):
        return func()
    return None


def indent(text: str):
    return textwrap.indent(text, dt.INDENT_LEVEL.get() * 2 * " ")


@contextmanager
def set_context[T](context: ContextVar[T], val: T):
    token = context.set(val)
    yield
    context.reset(token)


@t.final
class stfu[T: BaseException](AbstractContextManager[list[T]]):
    """
    Basically just like `suppress`. BUT - we get to have a reference of all of the exceptions
    that have been caught! That way we can re-raise them later

    ```python
     with stfu(AssertionError) as caught:
         assert foo()
         # bla bla bla
     # Execution still resumes here if the assert failed!
     if some_other_thing():
         raise ExceptionGroup("Yo! We messed up", caught)
    ```
    """

    def __init__(self, *exceptions: type[T]):
        self.caught: list[T] = []
        self._exceptions = exceptions

    # The lsp and the `basedpyright` command get this confused
    def __enter__(self):  # pyright: ignore[reportImplicitOverride]
        _ = super().__enter__()
        return self.caught

    @t.override
    def __exit__(  # pyright: ignore[reportIncompatibleMethodOverride]
        self,
        exctype: type[T] | None,
        excinst: T | None,
        _traceback: Traceback,
    ):
        # See http://bugs.python.org/issue12029 for more details
        if exctype is None:
            return
        if issubclass(exctype, self._exceptions):
            self.caught.append(excinst)  # pyright: ignore[reportArgumentType]
            return True
        if issubclass(exctype, BaseExceptionGroup):
            match, rest = t.cast(BaseExceptionGroup, excinst).split(self._exceptions)
            if rest is None:
                if match:
                    self.caught.extend(match.exceptions)  # pyright: ignore[reportArgumentType]
                return True
            raise rest
        return False


def to_valid_c_name(text: str) -> dt.Identifier:
    """
    Converts variables to valid C identifiers

    ```python
    >>> to_valid_c_name('..valid_``name')
    'valid_name'
    >>> to_valid_c_name('valid_name')
    'valid_name'
    >>> to_valid_c_name('1``11``1')
    ...
    AssertionError: Was your string just numbers???
    ```
    """
    # Convert to text just to make pyright happy
    assert isinstance(text, str), "Pydantic made a mistake brother!"
    quickly = "".join(re.findall(dt.Identifier_Pattern, text))
    # Ensure the first character starts
    while quickly and re.match(r"^[_a-zA-Z]", quickly) is None:
        quickly = quickly[1:]
    assert quickly, "Was your string just numbers???"
    return quickly


def flatten[T](*items: T | Iterable[T]) -> Iterable[T]:
    """Yield items from any nested iterable; see Reference."""
    for x in items:
        if isinstance(x, Iterable) and not isinstance(x, (str, bytes)):
            yield from flatten(*x)  # pyright: ignore[reportUnknownArgumentType]
        else:
            yield x  # pyright: ignore[reportReturnType]
