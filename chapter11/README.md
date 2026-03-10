# Chapter 11: Types Beyond Int! Long Integers

This chapter mostly focuses on laying out the groundwork needed to add the rest
of part 2 of the book, which focuses exclusively on types.

## Type Conversions

int -> long is ez-easy. We just have to ensure we use `movsx` to "move with sign extension"

long -> int is...well

> the new type is signed and the value cannot be represented in it[,] either
> the result is implementation-defined or an implementation-defined signal is
> raised.”

Implementation Defined!
IE: We do whatever the heck we want. The book enforces that we do the same thing as `gcc`

> “For conversion to a type of width N, the value is reduced modulo 2ⁿ to be
> within range of the type; no signal is raised”

The book says we'll just drop the top 4-bytes using `movl` from the long and be on our way.

```asm
# 11111111 11111111 11111111 11111111 11111111 11111111 11111111 11111101
movq $-3, %rex
# No problemo! Still -3
# 11111111 11111111 11111111 11111101
movl %ecx, %eax
```

```asm
# 00000000 00000000 00000000 00000000 10000000 00000000 00000000 00000000
movq $2147483648 , %rex
# It's negative now. Whatever :)
# 10000000 00000000 00000000 00000000
movl %ecx, %eax
```

## Static Longs

Almost the same as ints, but the `.align` is now `8` and the data is defined as `.quad`
