# Chapter 13: OH FUCK - FLOATS!

> Floating-point arithmetic is considered an esoteric subject by many people
>
> <cite>- David Goldberg</cite>
> [Source](https://www.itu.dk/~sestoft/bachelor/IEEE754_article.pdf)

(Technically we're only going to implement `double`, the C standard also defines
`float` and `long double` but the book tells us not to bother with them.)

TIL: The C-Standard doesn't exactly _say_ that you should use IEEE 754...but it's recommended
TIL: C compilers provide command line flags to control exactly how strictly we
conform to IEEE 754. My jank compiler won't bother, we'll just roughly match
the default behaviour of GCC/Clang (Ignoring floating-point exceptions and non default rounding modes).
TIL: Some operations are handled in hardware (`+` and `-`) while others require
`glibc` (remainder, square-root)

System V x64 ABI is very specific about float representation; so we'll just have to deal with that.

## IEEE 754 Double-Precision Float

TLDR: Grab yourself a python terminal and type the following:

```python
>>> (2.5).hex()
'0x1.4000000000000p+1'
```

ie: `-1**1 * (1 + 4 / 0x10 + 0 / 0x100 + 0 / 0x1000 ...) * 2**1`

THEM'S THE RULES.

The value of `(-1)^Sign × 1.F × 2ⁿ` is represented thusly in binary:

```
  Sign       Exponent        Fraction
(1 bit)     (11 bits)       (52 bits)
                            (sometimes called mantissa or significand)
┌┐╔╦╦╦═          ═╦╦╗ ┌┬┬┬─              ┬┬┐
││║║║║    ...     ║║║ ││││         ...   │││
└┘╚╩╩╩═          ═╩╩╝ └┴┴┴─              ┴┴┘
63              52                         0
```

(Note: This is a double because it's 64 bits, a normal float is only 32 bits)

Note that F (Binary Fraction, aka mantissa, significand) is analogous to a decimal number.
From the book:

> In decimal numbers, the digits to the left of the decimal point (the integer
> part) represent non-negative powers of 10, and the digits to the right (the
> fractional part) represent negative powers of 10: 1/10, 1/100, and so on.

So in our base-10 world: `12.34` is `1 * 10 + 2 * 10⁰ + 3 * 10⁻¹ + 4 10⁻²`

In binary, we're gonna use base-2...which creates difficulties.

For s start, our exponent is limited (and can be negative). So the `n` in `2ⁿ` is actually:

```
max = 2 ** size(exponent) - 1
n = signed_bits(exponent) - max - 1
```

AND - the integer part (before the dot) is always 1, the 52 bits we see
above encode only the fraction part (after the dot)

So we can neatly represent them thusly:

`x * 2**-1 + y * 2**-2 ... z * 2**-52`

From [this lovely
website](https://fabiensanglard.net/floating_point_visually_explained/) comes a
nicer explanation.

We'll rename the `exponent` to `window of binary-range` and the `fraction` to `specific`.

The `window` tells us which power of two we're aiming for, and the `F` tells us
WHERE in that range we're going to land on. Of course - because binary is an
ass this has some errors.

Table for ranges (32 bits since it's easier):

|                                                                                   |              |
| --------------------------------------------------------------------------------- | ------------ |
| [0.5, 1]                                                                          | [2⁻¹, 2⁰]    |
| [1, 2]                                                                            | [2⁰, 2¹]     |
| [2, 4]                                                                            | [2¹, 2²]     |
| ...etc                                                                            |              |
| [85070591730234615865843651857942052864, 170141183460469231731687303715884105728] | [2¹²⁶, 2¹²⁷] |

Precision is a formula, the larger the number the worse it is. Since there's a limited
amount of `specific` bits.

The formula is:

```
 range[1] - range[0]
--------------------
 2 ** bits_in_f
```

| Range              | 64-bit Precision       |
| ------------------ | ---------------------- |
| [0.5, 1]           | 1.1102230246251565e-16 |
| [1, 2]             | 2.220446049250313e-16  |
| [2, 4]             | 4.440892098500626e-16  |
| ...etc             |                        |
| [2**53, 2**52]     | 1                      |
| ...etc             |                        |
| [2**1022, 2**1023] | 9.9792015476736e+291   |

So precision looks grand! We need to get into the thousands of quadrillions before we lose a single int.

Examples:

2\*\*1023 is:

```
0111111111100000000000000000000000000000000000000000000000000000
```

Positive - No sign
10 `1s` on the Window (all `1s` is a special `inf` number)

From the formula above for n we get:

```python
n = 0b11111111110 - 1023
window = 2 ** n
```

No need to be specific, it lands exactly on a power of too, so we then have 53 zeroes.

```
number = 3.14
Positive, so sign is zero
In between 2-4


┌┐╔╦╦╦═          ═╦╦╗ ┌┬┬┬─              ┬┬┐
││║║║║    ...     ║║║ ││││         ...   │││
└┘╚╩╩╩═          ═╩╩╝ └┴┴┴─              ┴┴┘
  │                 │ │                    │
  └─────────────────┘ └─────────┬──────────┘
         │                      │
    ┌────┤                      │
    ▼    ▼                      │
0 1 2 3 4 5 6 7                 │
      ▲                         │
      └─────────────────────────┘
```

## Subnormal numbers

The smallest exponent we should be able to represent is `1 * 2**-1022`.
Right?...nope!

There's such a thing as `subnormal` numbers, when the exponent is all zeros then we're dealing with them.
Those little shits make a mess of our formula, because now it's no longer `1.F` but is instead
`0.F`. These guys are SUPER slow on hardware, so some C implementations provide a flag to round all of these
guys over to 0. (I mean...these dudes are 2e-308! The radius of the nucleus of an atom is 1e-15. Screw them)

## Infinity

Anything larger than 2\*\*1023 is rounded infinity. Infinity is also what we get when by by zero.

## NaN - Not a Number (_THE asshole_)

Represented by having all of the exponents set to 1 and a _non-zero_ fraction field.

NaN is what you get when you do undefined stuff in mathematics. So `0/0`. The
standard says that there's _signaling NaNs_ which raise an exception when used,
and _quiet NaNs_ which _don't_.

The fun thing about `NaNs` that everyone knows is that `NaN == NaN` evals to false!
This is because there are a lot of things that are undefined in mathematics,
and so comparing them should be false.

Mathematically: `1 / 0 == 0**0` are not the same! A programming language would _have_ to know
the expression that provided the `NaN` before it could be sure if they are equal.

Example

```lisp
; evals to false!
(equal '(/ 1 0) '(** 0 0))
; evals to true!
(equal '(/ 1 0) '(/ 1 0))
; No quotes - so we just compare the values
; The standard says that they eval to false
(equal (/ 1 0) (/ 1 0))
```

The extra-credit for this chapter is to implement `NaN`.

Why?
Because Nora Sandler ~is a sadistic asshole~ wants us to prove ourselves!

## Rounding

IEE 754 has many rounding modes. We'll only support the GCC default _round-to-nearest, ties-to-even_.
IE: A number is rounded towards the nearest number representable as a float, "ties-to-even" means that if a result
is exactly between two representable values it's rounded to the one whose least significant bit is 0.
We do this when converting constants and integers.

### Rounding Constants

Stuff like `0.1` can't be represented in binary, (similar to how we can't write 1/3 in decimal)

> IEEE 754 defines several decimal floating-point formats, which can represent
> decimal constants without this sort of rounding error. These formats encode
> numbers as decimal significands multiplied by powers of 10. C23 includes new
> decimal floating-point types that correspond to these formats.
>
> -- <cite>The book</cite>
