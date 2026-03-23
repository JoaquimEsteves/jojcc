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
