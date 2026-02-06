# Chapter-3 Diagram

Binary operations baby

## Parser problems

Expressions like this one make a mess of our parser `(1 + 2) * (3 + 4)` (or
bullshit with operator precedence).

The following wouldn't work:
`<exp> ::= <int> | <unop> <exp> | "(" <exp> ")" | <exp> <binop> <exp>`

Because it's ambiguous due to operator precedence and because we'd end-up with
unbound recursion.

(According to the book `left-resursive` rules can't be applied in a recursive
descent parser)

## Adequate Solution: Refactor the grammar

```
<exp> ::= <term> {("+" | "-") <term>}
<term> ::= <factor> {("*" | "/" | "%") <factor>}
<factor> ::= <int> | <unop> <factor> | "(" <exp> ")"
```

Note that the `{}` notation denotes 1 or more repetitions.

According to the book the issue with this is boilerplate:

> This approach works, but it gets increasingly unwieldy as you add more
> precedence levels. We have three precedence levels now, if you count
> `<factor>`; we’ll add four more when we introduce logical and relational
> operators in Chapter 4. If we went with this approach, we’d need to add a new
> symbol to the grammar—and a corresponding function to our parser—for each
> precedence level we add. That’s a lot of boilerplate, since the functions to
> parse the expressions at different precedence levels would be almost
> identical.

I'm actually kind of fine with boilerplate? I suspect that I'd be able to
refactor it properly, but watevs.

## Book Solution: Precedence Climbing

In this approach - every operator has a numeric precedence level and some
`parse_exp` function takes the minimum precedence level as an argument.

When the `parse_exp` sees some operator (`example +`) then it will parse the
right-hand-side but include only things that have a higher precedence than the
operator. (`TODO(Joaquim)`: I'm not sure I get it myself! - it _works_ but
unlike the lex/parse/tacky stuff I'm thoroughly confused here)

## Assembly Bullshit

Note the table:

| Instruction         | Meaning         |
| ------------------- | --------------- |
| `addl $2, %eax`     | `eax = eax + 2` |
| `subl $2, %eax`     | `eax = eax - 2` |
| `imull {@}$2, %eax` | `eax = eax * 2` |

This means that `subl a, b` computes `b - a` as opposed to the expected `a - b.`

**DIVISION IS GOD-AWFUL**

`add`, `subl`, `imull`, these all look clear and easy (except that ampersand on
the $2, the fuck is up with that?). But now comes the final boss - division!
For division apparently we're stuck with this jank `idiv` thing.

From the book: (With some notes in `{}` from _je_)

> We use `idiv` to implement the division and remainder operations. Even though
> you need two numbers to perform division, it takes a single operand: the
> divisor. (In `a / b`, a is the dividend and b is the divisor. {mfers like me
> will never actually remember which is which}).

> This operand can’t be an immediate value. In its 32-bit form, `idiv` gets the
> other value it needs, the dividend, from the `EDX` and `EAX` registers, which
> it treats as a single 64-bit value. It gets the most significant 32 bits from
> `EDX` and the least significant 32 bits from `EAX`. Unlike the other
> arithmetic instructions, `idiv` produces two results: the quotient and the
> remainder. It stores the quotient in `EAX` and the remainder in `EDX`. (The
> 64-bit version of `idiv`, written as `idivq`, uses `RDX` and `RAX` as the
> dividend instead of `EDX` and `EAX`.)

> To calculate `a / b` with `idiv`, we need to take `a` — which will be either
> a 32-bit immediate value or a 32-bit value stored in memory—and turn it into
> a 64-bit value spanning both `EDX` and `EAX`. Whenever we need to convert a
> signed integer to a wider format, we use an operation called sign extension.
> This operation fills the upper 32 bits of the new 64-bit value with the sign
> bit of the original 32-bit value.

Sign extension is pretty basic. Extend the left-hand thing over until we reach
the desired length.

> The `cdq` instruction does exactly what we want: it sign extends the value
> from `EAX` into `EDX`. If the number in `EAX` is positive, this instruction
> sets `EDX` to all zeros. If `EAX` is negative, it sets `EDX` to all ones.
> Putting it all together, as an example, the following assembly computes both
> 9 / 2 and 9 % 2:

```asm
# 9 / 2 AND 9 % 2
# 9 -> Dividend
# 2 -> divisor
movl   $2, -4(%rbp) ; slap the divisor over to _SOME_ memory address
                    ;   (In this case Stack-Base -4, could be whatever)
                    ;   P.S. How the heck do I do tiny locals in assembly?
                    '     I suppose if there is a `.global`, there must exist
                    ;     a `.local`
movl   $9, %eax     ; put the constant 9 into the special EAX register that
                    ;   `idivl` requires
cdq                 ; Sign-Extension
idivl  -4(%rbp)     ; Finally perform the division. 9/2 goes into EAX, while
                    ;   the remainder goes into EDX
```

This stores the result of 9 / 2, the quotient, in `EAX`. It stores the result
of 9 % 2, the remainder, in `EDX`.
