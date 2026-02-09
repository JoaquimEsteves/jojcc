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
    "MINUS",
    "PLUS",
    "ASTERISK",
    "FORWARD_SLASH",
    "PERCENT",
    "AMPERSAND",
    "PIPE",
    "CARRET",
    "LEFT_SHIFT",
    "RIGHT_SHIFT",
    "NOT",
    "AND",
    "OR",
    "EQUAL",
    "NEQUAL",
    "LT",  # less than
    "GT",  # greater than
    "LE",  # less or equal to
    "GE",  # greater or equal to
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
                "MINUS": r"-",
                "PLUS": r"\+",
                "ASTERISK": r"\*",
                "FORWARD_SLASH": r"/",
                "PERCENT": r"%",
                "CARRET": r"\^",
                "LEFT_SHIFT": r"<<",
                "RIGHT_SHIFT": r">>",
                "NEQUAL": r"!=",
                "NOT": r"!",
                "AND": r"&&",
                "AMPERSAND": r"&",
                "OR": r"\|\|",
                "PIPE": r"\|",
                "EQUAL": r"==",
                "LE": r"<=",  # less or equal to
                "LT": r"<",  # less than
                "GE": r">=",  # greater or equal to
                "GT": r">",  # greater than
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
