import pytest

from chapter8 import lexer, parser


def test_bad_while():
    hmm = lexer.lex("""
    while () ;
    """)

    with pytest.raises(AssertionError):
        _ = parser.Statement.from_tokens(hmm)

    missing_semicolon = lexer.lex("""
    do ; while(1)
    """)

    with pytest.raises(AssertionError):
        _ = parser.Statement.from_tokens(missing_semicolon)

    missing_body = lexer.lex("""
    do while(1);
    """)

    with pytest.raises(AssertionError):
        _ = parser.Statement.from_tokens(missing_body)


def test_while():
    hmm = lexer.lex("""
    while (1) ;
    """)

    neato = parser.Statement.from_tokens(hmm)
    assert neato and isinstance(neato[0].root, parser.While)

    hmm = lexer.lex("""
    do ; while (1);
    """)

    neato = parser.Statement.from_tokens(hmm)
    assert neato and isinstance(neato[0].root, parser.DoWhile)

    hmm = lexer.lex("""
    do {} while (1);
    """)

    neato = parser.Statement.from_tokens(hmm)
    assert neato and isinstance(neato[0].root, parser.DoWhile)


#
#
def test_good_for():
    hmm = lexer.lex("""
    for(a = 1; a < 2; ++a) { ; }
    """)

    _ = parser.Statement.from_tokens(hmm)[0]  # pyright: ignore[reportOptionalSubscript, reportUnknownVariableType]
    hmm = lexer.lex("""
    for(;;) { q + 1; return 5; }
    """)

    __ = parser.Statement.from_tokens(hmm)[0]  # pyright: ignore[reportOptionalSubscript, reportUnknownVariableType]

    hmm = lexer.lex("""
    for(;;) for(;;) { 1 + 1;return 1; }
    """)

    inner_loop = parser.Statement.from_tokens(hmm)[0]  # pyright: ignore[reportOptionalSubscript, reportUnknownVariableType]
    assert isinstance(inner_loop.root.body.root, parser.For)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert isinstance(inner_loop.root, parser.For)  # pyright: ignore[reportUnknownMemberType]


def test_if_expr():
    hmm = lexer.lex("1 ? (a = b) : 2")

    conditional = parser.Expression.from_tokens(hmm, assert_no_food_left=True)
    assert isinstance(conditional.type, parser.Conditional)
