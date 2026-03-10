import pytest

from chapter11 import lexer, parser


def test_functions():
    _ = parser.Program.from_tokens(
        lexer.lex("""
    int static foo(int hello, int there);
    int bar(int hello, int there) {
        int a = foo(1, 2);
    }
    extern int bar(int hello, int there) {
      for (int i; i > 2; i++) {
          ;
      }
      for (int i = 1; i > 2; i++) {
          ;
      }
      for (; i > 2; i++) {
          ;
      }
      int a = foo(1, 2);
      return 1;
    }
    int a = 2;
    static int a = 2;
    extern int b;
    """)
    )

    with pytest.raises(AssertionError):
        _ = parser.Program.from_tokens(
            lexer.lex("""
        static static foo(int hello, int there);
        """)
        )
