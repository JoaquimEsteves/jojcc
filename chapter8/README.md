# Chapter 8: Loops!

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
│║Variable Resolution║ │
│╚═══════════════════╝ │
│╔═══════════════════╗ │
│║  Loop Labelling   ║ │ <- New shit!
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

First of - there's the usual stuff of "the heck is a loop anyway"

```c
// only invokes `etc` if some_expression is false!
while (some_expression) {
  etc()
}
// always invokes `etc()`
do {
  etc()
} while (some_expression)
```

```
res = some_expr
jumpifzero END
call etc()
END:
...
```

Versus

```
START:
call etc()
res = some_expr
jumpifzero START
```

## Careful with the goddamn scopes

```c
int a = 5; // a0
for ( int a = 0; a < 5; a = a + 1) { // a1
    int a = 1; // a3
    b = b + a;
}
```
