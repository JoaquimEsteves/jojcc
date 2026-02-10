from collections.abc import Sequence, Iterator
from typing import get_args, TypeAliasType, cast


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

    def resolve(alias: TypeAliasType | tuple[T, ...] | T) -> Iterator[T]:
        match alias:
            case TypeAliasType():
                for val in resolve(get_args(alias.__value__)):  # pyright: ignore[reportAny]
                    yield from resolve(val)
                return
            case tuple():
                t_seq = cast(Sequence[T], alias)
                for element in t_seq:
                    yield from resolve(element)
                return
            case _:
                # Presume it's a `t.Literal`
                yield from resolve(get_args(alias))

        # Avoids yielding `t.Literal` again
        if not hasattr(alias, "__args__"):
            yield alias

    return frozenset(resolve(alias))
