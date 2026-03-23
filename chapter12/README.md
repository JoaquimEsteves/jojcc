# Chapter 12: Unsigned types baby!

## Signed T <-> Unsigned T

Doesn't change the binary representation of the number.

```c
#include <stdio.h>
#include <assert.h>
int main(void) {
    unsigned int a = -2;
    // prints 4_294_967_294 (-2 * 2**32)
    printf("%u\n", a);
    // compiler warning:
    // Implicit conversion from 'long' to 'int' changes value from 4294967294 to -2
    int b = 4294967294;
    assert(b == a);
    // Indeed - what we pring depends on the format!
    printf("%d\n", a);
    printf("%u\n", b);
    return 0;
}
```

If the leading bit is 0, then we don't need to do much except tweak the type-checker. All good!

If the leading bit is 1 however, that changes stuff! A negative number that
needs to be converted to an unsigned number will have 2ⁿ added to it; this
comes from the standard. If it was a large unsigned number that needs to be
signed then we subtract 2ⁿ from it, which is the same rule as GCC.

## Unsigned Comparisons

It's the goddamn `cmp` flag again! See `chapter4/README.md`

Some instructions (add, sub, cmp) don't care about the sign of our data, it's just bytes.
We just have to be consistent about what those bytes represent.

The problem comes when we look at the `RFLAGS`, those little nerds _do_ care
about the sign! The `SF` (Sign-Flag) tells us about a sign change, so if we did
`a - b` and the `SF` flag was 1 we'd know that `b` is bigger than `a`.

But that assumption goes out the window with unsigned numbers!

```
u8 a = 15
u8 b = 3
a - b = 12 (u8)

  1111
- 0011
------
  1100
```

The sign-flag for the previous operation would be set, but `b` is clearly not bigger than `a`!

So when we're dealing with unsigned numbers we'll ignore the `Overflow` and
`Sign` Flags, since they don't make any sense in the context.

So the `cmp` will instead instead look at the `Carry Flag` (`CF`).
Because we can't set the RFLAGS ourselves, that means using different instructions.

Like in chapter4, here's a table:

| Instruction | Meaning                        | ZF                | CF                |
| ----------- | ------------------------------ | ----------------- | ----------------- |
| sete        | Set If Equals (a == b)         | 1                 | -                 |
| setne       | Set If Not Equals (a != b)     | 0                 | -                 |
| seta        | Set if Above (a > b)           | 0                 | 0                 |
| setae       | Set if Above or equal (a >= b) | -                 | 0                 |
| setb        | Set if below (a < b)           | -                 | 1                 |
| setbe       | Set if below or equal (a <= b) | ZF set, or CF set | ZF set, or CF set |

It's pretty similar to the one mentioned in `chapter4/README.md`, instead of `greater` we use `above`.
Cute!

## Unsigned Division Is an Ass

Remember how all we had to do in the previous instructions was make a small
tweak since the other instructions remained the same?

Well not so with division!

```
  1000
/ 0010
------
  1100 (-4, if signed)
  0100 (4 if unsigned! They're completely different)
```

So when dealing with unsigned division we use `div` instead of `idiv`.
