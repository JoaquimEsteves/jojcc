"""
TODO(Joaquim): Export these so that the parser can also use them

(OR...just put the parser in the same file as the lexer?
150 lines on the parser ATM...not that many.
Maybe slap a `class Lex` as a little namespace?)
"""

import re
import typing as t

from shared import data_types as dt

type Token_Lexed = tuple[Token, str, dt.LineNo]
type Lexed = list[Token_Lexed]

WHITESPACE = re.compile(r"\s")

type Token = t.Literal[
    "INT_KEYWORD",
    "VOID_KEYWORD",
    "RETURN_KEYWORD",
    "IDENTIFIER",
    "CONSTANT",
    "OPEN_PARENS",
    "CLOSE_PARENS",
    "OPEN_BRACE",
    "CLOSE_BRACE",
    "SEMICOLON",
    "COMPLEMENT",
    "DECREMENT",
    "NEGATION",
]

TOKEN_REGEX = t.cast(
    dict[Token, re.Pattern[str]],
    {
        key: re.compile(val)  # re.compile supposedly makes stuff faster
        for key, val in (
            {
                # Note: The book says that we should treat `keywords` as identifiers I'm
                # instead gonna cheat lol. Trying to make it so that we check for keywords
                # _FIRST_ and _THEN_ We check for identifiers I suspect that in the future
                # this won't work, as the user will have their own typedefs and other stuff
                "INT_KEYWORD": r"int\b",
                "VOID_KEYWORD": r"void\b",
                "RETURN_KEYWORD": r"return\b",
                "IDENTIFIER": r"[a-zA-Z_]\w*\b",
                "CONSTANT": r"[0-9]+\b",
                "OPEN_PARENS": r"\(",
                "CLOSE_PARENS": r"\)",
                "OPEN_BRACE": r"{",
                "CLOSE_BRACE": r"}",
                "SEMICOLON": r";",
                "COMPLEMENT": r"~",
                "DECREMENT": r"--",
                "NEGATION": r"-",
            }
        ).items()
    },
)


def lex(input: str):
    lexed: Lexed = []
    lineno = 0

    def inner(current: str, lineno: dt.LineNo):
        for token, regex in TOKEN_REGEX.items():
            match = regex.match(current)
            if match is None:
                continue
            lexed.append(
                # if DEBUG add the `rest`
                (token, current[slice(*match.span())], lineno),
            )
            return current[match.end() :], lineno + match.end()
        raise ValueError("Syntax Error")

    while input != "":
        if WHITESPACE.match(input):
            input = input.lstrip()
            continue
        input, lineno = inner(input, lineno)

    return lexed
