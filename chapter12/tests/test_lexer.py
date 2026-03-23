from shared import pure_functions as pf
from chapter12 import lexer


def test_ensure_all_tokens_in_dict():
    missing: list[str] = []
    for i in pf.get_literal_vals(lexer.Token):
        i_s = str(i)
        if i_s not in lexer.TOKEN_REGEX:
            missing.append(i_s)

    assert missing == [], "Missing some tokens!"
