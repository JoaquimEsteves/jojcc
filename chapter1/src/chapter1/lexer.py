import re

type Token = str
type Lexed = list[Token]

WHITESPACE = re.compile(r"\s")

TOKEN_REGEX = {
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
        }
    ).items()
}


def lex(input: str):
    lexed: Lexed = []

    def inner(current: str):
        for token, regex in TOKEN_REGEX.items():
            match = regex.match(current)
            if match is None:
                continue
            lexed.extend(
                # if DEBUG add the `rest`
                [token, current[slice(*match.span())]],
            )
            return current[match.end() :]
        raise ValueError("Syntax Error")

    while input != "":
        if WHITESPACE.match(input):
            input = input.lstrip()
            continue
        input = inner(input)

    return lexed

