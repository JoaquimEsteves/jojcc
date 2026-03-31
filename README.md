# jojcc

> Joaquim's Own Jank C Compiler

Effectively I'm going through the book [Writing a C Compiler](https://nostarch.com/writing-c-compiler).

I strongly recommend the book. It's a _workbook_, the author-lady will just
tell you "Alright, you're on your own now buddy". Extra-Credit sections are the
most fun, since there's no hand-holding whatsover. (Pre & Postfix operators
were invented by the devil, Nora Sandler was sadistic to leave those as
homework)

At the time of writing the book costs 69.99$, but I got it from a Humble-Bundle
deal for considerably less money.

## Get the submodules

```bash
$ git submodule init
$ git submodule update
```

## Install/Running guides

See the makefile

## Neat documents

- [From the author herself](https://norasandler.com/book/)
- [Draft of the C23 standard](https://www.open-std.org/JTC1/SC22/WG14/www/docs/n2310.pdf)
  It's the draft since (as the book points out) the real deal costs 200$ (lol)
- [System V ABI](https://gitlab.com/x86-psABIs/x86-64-ABI)
  Calling conventions
- [Unofficial intel 64 developers manual](https://www.felixcloutier.com/x86/)
  - [How to read it (it's not trivial lol)](https://stackoverflow.com/questions/59622640/how-to-read-x86-instruction-tables-from-this-site)

## Every x64 Register With Pictures

[Confused about the naming convention of registers? So was I!](https://keleshev.com/eax-x86-register-meaning-and-history/)

8 bit in 1972, 16 bit in 1979

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

 ┌──────┐
 │  IP  │       Instruction Pointer          NOPE?
 └──────┘       (Can't be touched by us)
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
 │ EIP │
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
 ║ RIP ║
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

## XMM REGISTERS BABY

XMM Registers are the ones used for SSE (Signed SIMD (Single Instruction,
Multiple Data) Extension) instructions. They are a whopping 128 bit wide!
This is what the folks in the know call `non-general-purpose registers`.

They are simply XMM0, XMM1, ..., XMM15.

Invented circa 1999 by the Intel nerds, there were supposed to replace some
other MMX registers.

(Note: Recently there's even the YMM and ZMM registers!
[Stack overflow has a good post about it](https://stackoverflow.com/a/44299695/6595024))

As the name indicates they were an _extension_, they only became part of the
core x64 instruction set after a while.

They are also used in a variety of operations, not just floating-point stuff.
When we ask GCC what's in some XMM register it'll reply _"Oh boy - there's
options!"_

```
(gdb) // annotated and tweaked formatting
(gdb) print $xmm0
$4 = {
  // 4 32 bit floats packed into a single register.
  v4_float = {0, 2.1875, 0, 0},
  // 2 doubles
  v2_double = {3.5, 0},
  // 16 int8s
  v16_int8 = {0, 0, 0, 0, 0, 0, 12, 64, 0, 0, 0, 0, 0, 0, 0, 0},
  // ...etc
  v8_int16 = {0, 0, 0, 16396, 0, 0, 0, 0},
  v4_int32 = {0, 1074528256, 0, 0},
  v2_int64 = {4615063718147915776, 0},
  uint128 = 4615063718147915776
}
```
