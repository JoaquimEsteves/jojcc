from chapter9 import lexer, parser


def test_functions():
    _ = parser.Program.from_tokens(
        lexer.lex("""
    int foo(int hello, int there);
    int bar(int hello, int there) {
        int a = foo(1, 2);
    }
    """)
    )
