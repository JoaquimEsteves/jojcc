import chapter4.parser
import chapter4.lexer

import chapter5.parser
import chapter5.lexer


def test_left_assoc():
    expression, rest = chapter5.parser.Expression.parse(chapter5.lexer.lex("a + b - c"))
    assert repr(expression) == "(MINUS (PLUS `a` `b`) `c`)"
    assert rest == []

    expression, rest = chapter5.parser.Expression.parse(
        chapter5.lexer.lex("a + b * c; irrelevant_with_utf_8_λ")
    )
    assert repr(expression) == "(PLUS `a` (ASTERISK `b` `c`))"

    assert [i[0] for i in rest] == ["SEMICOLON", "IDENTIFIER"]


def test_right_assoc():
    expression = chapter5.parser.Expression.parse(
        chapter5.lexer.lex("a = b = c + d"), assert_no_food_left=True
    )
    assert repr(expression) == "(= `a` (= `b` (PLUS `c` `d`)))"


def test_both():
    expression = chapter5.parser.Expression.parse(
        chapter5.lexer.lex("a + b * (oi = c + d)"), assert_no_food_left=True
    )
    assert repr(expression) == "(PLUS `a` (ASTERISK `b` (= `oi` (PLUS `c` `d`))))"


def test_left_assoc_chapter4():
    expression = chapter4.parser.Expression.parse(chapter4.lexer.lex("1 + 2 - 3"))
    assert repr(expression) == "(MINUS (PLUS 1 2) 3)"

    expression = chapter4.parser.Expression.parse(chapter4.lexer.lex("1 + 2 * 3"))
    assert repr(expression) == "(PLUS 1 (ASTERISK 2 3))"
