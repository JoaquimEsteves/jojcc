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

TIL: assignment `=` is an expression! This is totally valid c:

```c
int a;
int b = 2 * (a = 5);
```

That's the reason why we can do `a = b = c = 2`
