import pytest

from chapter7 import lexer, parser


def test_if_statement():
    hmm = lexer.lex("""
    if (a)
        if (a > 10)
            return a;
    else
        return 10 - a;

    """)

    neato = parser.Statement.from_tokens(hmm)
    assert neato and isinstance(neato[0].root, parser.IfStatement)


def test_bad_if_statement():
    hmm = lexer.lex("""
    if a return a;

    """)

    with pytest.raises(AssertionError):
        _ = parser.Statement.from_tokens(hmm)


def test_if_expr():
    hmm = lexer.lex("1 ? (a = b) : 2")

    conditional = parser.Expression.from_tokens(hmm, assert_no_food_left=True)
    assert isinstance(conditional.type, parser.Conditional)
