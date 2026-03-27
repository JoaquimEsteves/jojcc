# Chapter-4: Logical and Relational Operators

We're gonna add a BUNCH of binary and unary operators.

We have `NOT(!)`, `AND(&&)` and `OR(||)`, as well as relational operators
`<,>,== (etc)`.

## AND OR Short-circuit

If we know that the left-handside of these bad-boys we can sometimes skip the
second. (This is not an optimization - it's straight up part of the standard)
That means JUMPS baby!

## Comparison

All `conditional` instructions rely on the state of the `RFLAGS` register.

You can inspect them in `gdb` using `$eflags`, see [wikipedia](https://en.wikipedia.org/wiki/FLAGS_register)

These nerds are special, since we can't set it ourselves, instead the CPU updates
it whenever some `conditional` instruction happens.

(Makes sense, consider that all instructions are `(func a b)`, there's no room
to put the return of some `<`)

The relevant ones for the book are:

**RFLAGS**

- Zero Flag(ZF).
  - Did the last instruction yield zero?
  - ex: `1 == 0 => False! ZF is 1`
  - ex: `1 != 0 => True! ZF is 0`
- Sign Flag (SF)
  - Is the first bit of the last instruction a 1?
  - (Naturally irrelevant if the previous instruction was unsigned)
  - Ex: `-1 - 2 => -3. Sign flag is 1`
  - Ex: `-1 + 2 => 1. Sign flag is 0`
- Overflow Flag (OF)
  - Did the last instruction overflow?
  - ex: `INT_MAX + whatever => Overflow! OF is 1`
  - ex: `unsigned(MAX) + 1 => NO IDEA (But irrelevant)`

Here's when Overflow _CAN_ happen

(In addition, if they have the same sign we _CAN_ overflow!)

| A     | B     | Operation | Overflow?         |
| ----- | ----- | --------- | ----------------- |
| a > 0 | b > 0 | `a + b`   | YEP! `max + 1`    |
| a < 0 | b > 0 | `a + b`   | NOPE              |
| a > 0 | b < 0 | `a + b`   | NOPE              |
| a < 0 | b < 0 | `a + b`   | YEP! `min + (-1)` |

(In subtraction - if they have different signs then we _CAN_ overflow.)

| A     | B     | Operation | Overflow?         |
| ----- | ----- | --------- | ----------------- |
| a > 0 | b > 0 | `a - b`   | NOPE              |
| a < 0 | b > 0 | `a - b`   | YEP! `min - (+1)` |
| a > 0 | b < 0 | `a - b`   | YEP! `max - (-1)` |
| a < 0 | b < 0 | `a - b`   | NOPE              |

> OK, but like. Who cares?

The problem is that the `cmp` instruction executes EXACTLY like the `sub`! So
has the same impact on the RFLAGS

So we need to check these silly flags to ensure that our `cmp` didn't crap the bed due to some overflow.

```
cmp a, b
```

| A in relation to B | Overflow?         | ZF  | OF  | SF  |
| ------------------ | ----------------- | --- | --- | --- |
| a == b             | (never overflows) | 1   | 0   | 0   |
| a > b              | NOPE              | 0   | 0   | 0   |
| a > b              | YEP               | 0   | 1   | 0   |
| a < b              | NOPE              | 0   | 0   | 1   |
| a < b              | YEP               | 0   | 1   | 0   |

So `a >= b` if `SF==OF`

Conditional Seet and flags

| Instruction | Meaning                          | ZF      | OF  | SF  |
| ----------- | -------------------------------- | ------- | --- | --- |
| sete        | Set If Equals (a == b)           | changes | -   | -   |
| setne       | Set If Not Equals (a != b)       | changes | -   | -   |
| setg        | Set if Greater (a > b)           | 0       | 1   | 0   |
| setge       | Set if Greater or equal (a >= b) | 0       | 0   | 1   |
| setl        | Set if less (a < b)              | 0       | 1   | 0   |
| setle       | Set if less or equal (a <= b)    | 0       | 1   | 0   |

Note: These `set` flags MUST operate at a byte level.
So we want to set `%eax` we'll instead need to target `%al`, which is the last
byte of the `%eax` register (HOW DOES ANYONE REMEMBER THIS SHIT??)

Example:

```
movl $2, $edx
cmpl $1, $edx
; 1 == 2?
sete %al  ; p/t %eax will print 11111111111111111111111100000000
; 1 < 2?
setl %al  ; p/t %eax will print 11111111111111111111111100000001
```

## Jumps Baby

Jumps operate in much the same way as the `set` boys, except that they jump to
some label if the condition is true.

### Inspecting this stuff with good ol' GDB

Aquire some assembly file. For example:

```asm
; file yo.s
.type	main, @function
main:
	pushq    %rbp
	movq     %rsp, %rbp
	movl $-2, %eax
	cmpl $-1, %eax
	sete %al
	setl %al

	movq %rbp, %rsp
	popq	%rbp
	ret
.section .note.GNU-stack,"",@progbits
```

Compile and run thusly: `gcc --debug yo.s && gdb a.out`

Then `tui reg all` and `break main`.
Usual debugging then ensues, top tip is `p/t $eax`. This will print the
register in binary format.

The special `$eflags` variable shows us which of these flags is one.

```
# (gdb) p $eflags
# $2 = [ PF ZF IF ]
movl $2147483647, %eax
# (gdb) p $eflags
# $3 = [ PF AF SF IF OF ]
# Sign flipped and the overflow sign is there!
```
