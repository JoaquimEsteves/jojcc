# Baby First Diagram

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
└───────┘
   │
   │  AST
   │
┌──▼────────────────┐
│Assembly Generation│
└──┬────────────────┘
   │  Assembly
   │
┌──▼──────────┐ 
│Code Emission│ 
└──┬──────────┘ 
   ▼
program.s
```
