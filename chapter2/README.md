# Chapter-2 Diagram

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

# Negation and Bitwise Complement

- In this chapter we add negation (`-<int>`) and bitwise complement (`~<int>`, flips every bit)

```assembly
// Given int main(void) { return ~(-2); }

 .globl main
main:
    pushq   %rbp          ; Setup the Register-Base
    movq     %rsp, %rbp   ; Stack-Pointer is the same as Register-Base
    subq     $8, %rsp     ; Decrement the stack-pointer by 8 (two int vars)
  ❶ movl     $2, ❷ -4(%rbp) ; Move the constant `2` over to some address in memory
                            ; This address will be on the stack
  ❸ negl     -4(%rbp)     ; Negate 2
  ❹ movl     -4(%rbp), %r10d ; Move the negative 2 over to some new address of -8 bellow the stack
                             ; We need two instructions for this, because `mov`` can't have memory addresses
                             ; as both it's source and destination
                             ; So we first move -2 over to a SCRATCH REGISTER (r10d)
                             ; From r10d we move it to where we want
  ; Why not do everything on -4(%rbp) directly? No idea lol
  ; I suppose we'll deal with that on the optimization section in future chapters
  ❺ movl     %r10d, -8(%rbp)
  ❻ notl     -8(%rbp)     ; bitwise complement
  ❼ movl     -8(%rbp), %eax ; finally - move it over to EAX (to return it) and clean up the stack
    movq     %rbp, %rsp  ; Stack restore. The Stack-Pointer is now the same as the Base-Pointer
    popq     %rbp        ; Increment the base by 8, getting rid of our two vars.
    ret
```

**Register-Stack-Pointer (RSP)** -> Always holds the address at the top of the (current) stack.
**Register-Base-Pointer (RBP)** -> Points to the base of the current stack frame (by convention)
Most production compilers optimize the RBP away, using only the `RSP`, but for
a n00b like me RBP is pretty cool.

`push X` does two things.

- Writes the value being pushed (X) to the next empty spot on the stack.
  - The push/pop adjust the stack pointer in 8-byte increments. So the next
    empty spot after a `PUSH` is `RSP-8` (this book uses negative offset, to me
    it makes more sense that we increment it, but what can ya ya do lol)
- Decrements the RSP by 8. The address in RSP is now the top of the stack, and
  the value is X

Example

```
BEFORE

RSP: ─────────────►  a 0x08
                     b 0x16
                     c 0x24
```

`push $3`

```
After

RSP: ─────────────►   3 0x00
                      a 0x08
                      b 0x16
                      c 0x24
```

Note this -4 business. push/pop are always 8-bytes, but ints are 4 bytes!

But that's OK 'cos we can just `movl` to copy some 4-byte value (like an int)
into stack space we've already allocated.

So all functions begin by first invoking `push` N times, and then moving the
values over to their spots on the stack.

| Fake-C         | Fake Assembly                                   |
| -------------- | ----------------------------------------------- |
| `i64 foo = 0`  | `push $0`                                       |
| `i32 foo = -1` | `push $0`; `movl $-1 RBP-8` OR `movl $-1 RSP+8` |
