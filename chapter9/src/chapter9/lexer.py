import re
import typing as t

from shared import data_types as dt
from shared.pure_functions import get_literal_vals


def lex(input: str):
    lexed: Lexed = []
    charno = 0
    """
    Just realised that this whole charno is really wrong.
    Forgot about the fact that I do an `lstrip`.
    Whatever.
    """

    def inner(current: str, charno: dt.CharNo):
        for token, regex in TOKEN_REGEX.items():
            match = regex.match(current)
            if match is None:
                continue
            lexed.append(
                # if DEBUG add the `rest`
                (token, current[slice(*match.span())], charno),
            )
            return current[match.end() :], charno + match.end()
        raise ValueError("Syntax Error")

    while input != "":
        if WHITESPACE.match(input):
            input = input.lstrip()
            continue
        input, charno = inner(input, charno)

    return lexed


type Token_Lexed = tuple[Token, str, dt.CharNo]
type Lexed = list[Token_Lexed]

WHITESPACE = re.compile(r"\s")

type Token = t.Literal[
    "DO_KEYWORD",
    "WHILE_KEYWORD",
    "FOR_KEYWORD",
    "SWITCH_KEYWORD",
    "CASE_KEYWORD",
    "DEFAULT_KEYWORD",
    "BREAK_KEYWORD",
    "CONTINUE_KEYWORD",
    "INT_KEYWORD",
    "VOID_KEYWORD",
    "GOTO",
    "GOTO_LABEL",
    "IF_KEYWORD",
    "ELSE_KEYWORD",
    "RETURN_KEYWORD",
    "IDENTIFIER",
    "CONSTANT",
    "OPEN_PARENS",
    "CLOSE_PARENS",
    "{",
    "}",
    ",",
    "SEMICOLON",
    "COMPLEMENT",
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
    "?",
    ":",
    "==",
    "!=",
    "LT",  # less than
    "GT",  # greater than
    "LE",  # less or equal to
    "GE",  # greater or equal to
    "=",
    # Compound assignment
    "+=",
    "-=",
    "*=",
    "%=",
    "&=",
    "|=",
    "^=",
    "<<=",
    ">>=",
    # increment and decrement fancyness
    # OPERATORS: I have no idea how to do them lol
    # TODO(Joaquim): Continue reading the book and go back to this
    "++",
    "--",
]

Fancy_Assignment_Ops = t.Literal[
    "+=", "-=", "*=", "%=", "&=", "|=", "^=", "<<=", ">>=", "/="
]

Assignment_Ops = t.Literal["=",] | Fancy_Assignment_Ops

ASSIGNMENT_OPS = tuple(
    t.cast(frozenset[Assignment_Ops], get_literal_vals(Assignment_Ops))
)


TOKEN_REGEX = t.cast(
    dict[Token, re.Pattern[str]],
    {
        key: re.compile(val)  # re.compile supposedly makes stuff faster
        for key, val in (
            {
                # Note: The book says that we should treat `keywords` as identifiers I'm
                # instead gonna cheat lol. Trying to make it so that we check for keywords
                # _FIRST_ and _THEN_ we check for identifiers. I suspect that in the future
                # this won't work, as the user will have their own typedefs and other stuff
                "DO_KEYWORD": r"do\b",
                "WHILE_KEYWORD": r"while\b",
                "FOR_KEYWORD": r"for\b",
                "SWITCH_KEYWORD": r"switch\b",
                "CASE_KEYWORD": r"case\b",
                "DEFAULT_KEYWORD": r"default\b",
                "BREAK_KEYWORD": r"break\b",
                "CONTINUE_KEYWORD": r"continue\b",
                "INT_KEYWORD": r"int\b",
                "VOID_KEYWORD": r"void\b",
                "IF_KEYWORD": r"if\b",
                "ELSE_KEYWORD": r"else\b",
                "RETURN_KEYWORD": r"return\b",
                "GOTO": r"goto\b",
                "GOTO_LABEL": r"[a-zA-Z_]\w*:\b:",
                "IDENTIFIER": r"[a-zA-Z_]\w*\b",
                "CONSTANT": r"[0-9]+\b",
                ",": r"\,",
                "OPEN_PARENS": r"\(",
                "CLOSE_PARENS": r"\)",
                "{": r"{",
                "}": r"}",
                "SEMICOLON": r";",
                "COMPLEMENT": r"~",
                "?": r"\?",
                ":": r"\:",
                "--": r"--",
                "-=": r"\-=",
                "MINUS": r"-",
                "+=": r"\+=",
                "++": r"\+\+",
                "PLUS": r"\+",
                "*=": r"\*=",
                "ASTERISK": r"\*",
                "/=": r"/=",
                "FORWARD_SLASH": r"/",
                "%=": r"%=",
                "PERCENT": r"%",
                "^=": r"\^=",
                "CARRET": r"\^",
                "<<=": r"<<=",
                "LEFT_SHIFT": r"<<",
                ">>=": r">>=",
                "RIGHT_SHIFT": r">>",
                "!=": r"!=",
                "NOT": r"!",
                "AND": r"&&",
                "&=": r"&=",
                "AMPERSAND": r"&",
                "OR": r"\|\|",
                "|=": r"\|=",
                "PIPE": r"\|",
                "==": r"==",
                "=": r"=",
                "LE": r"<=",  # less or equal to
                "LT": r"<",  # less than
                "GE": r">=",  # greater or equal to
                "GT": r">",  # greater than
            }
        ).items()
    },
)
