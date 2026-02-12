from collections.abc import Sequence, Iterator
from contextvars import ContextVar
import typing as t
import textwrap

from pydantic import BaseModel, ValidationError
from contextlib import contextmanager
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

    return frozenset(resolve(alias))


def try_model[T: BaseModel](cls: type[T], **args: t.Any):
    """
    Tries to build some pydantic module, or returns None
    """
    try:
        return cls(**args)
    except ValidationError, AssertionError:
        return None


def indent(text: str):
    return textwrap.indent(text, dt.INDENT_LEVEL.get() * 2 * " ")


@contextmanager
def set_context[T](context: ContextVar[T], val: T):
    token = context.set(val)
    yield
    context.reset(token)
