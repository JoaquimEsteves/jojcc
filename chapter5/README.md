# Chapter-5: Local Variables!

```
program.c
   │
   │
┌──▼──┐
│Lexer│
└──┬──┘
   │
   │  Token List
   │
┌──▼────┐
│Parser │
└──┬────┘
┌──▼───────────────────┐
│Semantic Analysis     │
│╔═══════════════════╗ │
│║Variable Resolution║ │   <- New shit!
│╚═══════════════════╝ │
└──┬───────────────────┘
   │
   │  AST
   │
 ┌─▼──────────────┐
 │TACKY GENERATION│
 └─┬──────────────┘
   │
┌──▼─────────────────────────────────┐
│ Assembly Generation                │
│ ╔════════════════════════════╗     │
│ ║Converting TACKY to assembly║     │
│ ╚════════════════════════════╝     │
│ ╔════════════════════════════╗     │
│ ║  Replacing pseudoregisters ║     │
│ ╚════════════════════════════╝     │
│ ╔════════════════════════════╗     │
│ ║ Instruction fix-up         ║     │
│ ╚════════════════════════════╝     │
└──┬─────────────────────────────────┘
   │  Assembly
   │
┌──▼──────────┐
│Code Emission│
└──┬──────────┘
   ▼
program.s
```

## TIL

### assignment `=` is an expression!

This is totally valid c:

```c
int a;
int b = 2 * (a = 5);
```

That's the reason why we can do `a = b = c = 2`

### Declarations are not statements!

Declarations are a separate AST node, not another kind of statement, because
declarations aren’t statements! Conceptually, the difference is that statements
are executed when the program runs, whereas declarations simply tell the
compiler that some identifier exists and can be used later.

Practically this means that this is invalid:

```c
if (a == 2) {
  int x = 0;
}
```

`gcc` will complain, but `clang` doesn't give a shit.

## Right vs Left Associativity

It's effectively _how should we order our list?_

In left-associativity when we find something with the same precedence on the right
We stop and yield back the expression.

Example: `a + b * c` -> `a + (b * c)` -> `(+ a (* b c))`
With RIGHT we want to continue when we find something with the same precedence!
Example: `a = b = d + c` -> `a = b = (d + c)` -> `(= a (= b (+ d c)))`

Note that with `left-assoc` we eval the expression on the left first, but with
`right-assoc` we do the one on the right first.

The algorithm is pretty simple, but hard to grok because of goddamn recursion.

In both cases, we keep a counter of the current token precendence. We
recursively call the function but increment said counter for left-assoc and
don't touch it if it's right-assoc.

More examples:

`a + b * (oi = c + d)` -> `a + (b * (oi = (c + d)))` -> `(+ a (* b (= oi (+ c d))))`

I'm...still quite confused about the whole thing. I wanted to try to rewrite
the algorithm so it wasn't recursive, but alas it turend out to be quite
tricky.
