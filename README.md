# jojcc

> Joaquim's Own Jank C Compiler

Effectively I'm going through the book [Writing a C Compiler](https://nostarch.com/writing-c-compiler).

I strongly recommend the book. It's a _workbook_, the lady will just tell you
"Alright, you're on your own now buddy". Extra-Credit sections are the most fun, since there's no hand-holding whatsover.
(Pre & Postfix operators were invented by the devil)

I got it from a Humble-Bundle deal, 'cos otherwise the fekin' thing costs 69.99$ at the time of writing (Jesus!).

## Get the submodules

```bash
$ git submodule init
$ git submodule update
```

## Install/Running guides

See the makefile

## Neat documents

- [Draft of the C23 standard](https://www.open-std.org/JTC1/SC22/WG14/www/docs/n2310.pdf)
  It's the draft since (as the book points out) the real deal costs 200$ (lol)
- [System V ABI](https://gitlab.com/x86-psABIs/x86-64-ABI)
  Calling conventions
- [Unofficial intel 64 developers manual](https://www.felixcloutier.com/x86/)
  - [How to read it (it's not trivial lol)](https://stackoverflow.com/questions/59622640/how-to-read-x86-instruction-tables-from-this-site)

## Every x64 Register With Pictures

[Confused about the naming convention of registers? So was I!](https://keleshev.com/eax-x86-register-meaning-and-history/)

_1979_

```
◄─ 16 Bit ─►   Mnemonic                   ◄═8 BIT═► (each box!)

 ┌──────┐                                 ╔════╦════╗
 │  AX  │       ACCUMULATOR               ║AH  ║  AL║
 ├──────┤                                 ╠════╬════╣
 │  BX  │       BASE                      ║BH  ║  BL║
 ├──────┤                                 ╠════╬════╣
 │  CX  │       COUNTER                   ║CH  ║  CL║
 ├──────┤                                 ╠════╬════╣
 │  DX  │       DATA                      ║DH  ║  DL║
 ├──────┤                                 ╚════╩════╝
 │  SP  │       STACK POINTER                NOPE!
 ├──────┤
 │  BP  │       BASE (of stack)              NOPE!
 ├──────┤
 │  SI  │       SOURCE INDEX                 NOPE!
 ├──────┤
 │  DI  │       DESTINATION INDEX            NOPE!
 └──────┘
```

H stands for `HIGH` and `L` stands for low!
So:

```
AX -> 0000000011111111
      ───┬────════╦═══
         │        ║
         ▼        ║
         AH       ▼
                  AL
```

_1985_
(E is for EXTENDED)

```
 ◄─ 32 Bit ─►
 ┌─────┐
 │ EAX │
 ├─────┤
 │ EBX │
 ├─────┤
 │ ... │
 ├─────┤
 │ EDI │
 └─────┘
```

_2003_
R just stands for REGISTER, which is stupid since `E` (the smaller) stands for EXTENDED.

```
◄═ 64 Bit ═►

 ╔═════╗
 ║ RAX ║
 ╠═════╣
 ║ RBX ║
 ╠═════╣
 ║ ... ║
 ╠═════╣
 ║ RDI ║
 ╚═════╝
```

We then got 8 new registers, R8 to R15. They kept the old ones around
because people liked the mnemonics and decided to invent new (shittier) mnenomics.

```

◄───── 64 bits ───────────
     ◄─ 32 bits ──────────
              ◄─16 bits ──
                    ◄─ 8 ─
╔════╦══════╦══════╦══════╗
║R15 ║ R15D ║ R15W ║ R15B ║
╚════╩══════╩══════╩══════╝
```

- `D` -> `Double`
- `W` -> `Word`
- `B` -> `Byte`
- `<nada>` -> `Register`

Cool thing they did was they now allow us to reference the low-high parts that
32 bits didn't allow.
