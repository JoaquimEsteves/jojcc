# Chapter 10: File Scope Variable Declarations & Storage-Class Specifiers

All about `static/extern` (other stuff like `auto, register, _Thread_local` and
`typedef` won't be implemented)

Terminology from the book

> 1.  A file or source file is a preprocessed source file, referred to in the C
>     standard (and the previous chapter) as a "translation unit."
> 2.  A static variable is a variable with static storage duration (discussed in
>     Storage Duration” on page 212), not just a variable declared with the static
>     storage-class specifier. All variables with the static specifier are static
>     variables, but not all static variables are declared with that specifier.
> 3.  An automatic variable is a variable with automatic storage duration (also
>     discussed in "Storage Duration"), as opposed to static storage duration. All
>     the variables we encountered in earlier chapters were automatic variables.
> 4.  An external variable is any variable with internal or external linkage, not
>     just a variable declared with the extern storage-class specifier. As we’ll
>     see, all external variables are also static variables, but not all static
>     variables are external.

## The Table For Variable Declarations

| #   | Scope | Specifier | Linkage                                             | Storage Duration | WITH initializer | NO initializer                  |
| --- | ----- | --------- | --------------------------------------------------- | ---------------- | ---------------- | ------------------------------- |
| 0   | File  | None      | External                                            | Static           | Yes              | Tentative                       |
| 1   | File  | `static`  | Internal                                            | Static           | Yes              | Tentative                       |
| 2   | File  | `extern`  | Previous visible declaration, default to `external` | Static           | Yes              | No                              |
| 3   | Block | None      | None                                                | Automatic        | Yes              | Yes (defined but uninitialized) |
| 4   | Block | `static`  | None                                                | Static           | Yes              | Yes (set to 0)                  |
| 5   | Block | `extern`  | Previous visible declaration, default to `external` | Static           | INVALID          | No                              |

Examples

```
// 0
int a; // TENTATIVE
int a = 0;
// 1
static a; // TENTATIVE
static a = 1; // initialized.
// 2
extern a;
//  3
{
   int a; // uninitialized
}
// 4
{
   static int a; // same as static int a = 0;
}
// 5
{
   extern int a;
}
```

## The Table For Function Declarations

| #   | Scope | Specifier        | Linkage                                             | WITH body | NO body |
| --- | ----- | ---------------- | --------------------------------------------------- | --------- | ------- |
| 0   | File  | None (or extern) | Previous visible declaration, default to `external` | Yes       | No      |
| 1   | File  | `static`         | Internal                                            | Yes       | No      |
| 2   | Block | None (or extern) | Previous visible declaration, default to `external` | INVALID   | No      |
| 3   | Block | `static`         | INVALID                                             | INVALID   | INVALID |

Examples:

```
// 0
int foo() // can be external or internal. Body or no makes no difference
// 1
static int foo() // always internal linkage. Body or no makes no difference
// 2
{
   int foo(); // can be external or internal. Body is illegal
}
// 3
{
   static int foo(); // always illegal
}

```

## Static and Linkage

If we declare a function/variable to be `static` then that little guy has no external linkage.

```c
// file a.c
int foo(void) {
   return bar();
}

int bar(void) {
   return 1;
}
// file b.c
int foo(void);
static int bar(void);

int main(void) {
    return foo() + bar();
}

// This bar can NOT be used outside of b.c
static int bar(void) {
    return 4;
}
```

Effectively:

```c
int foo(void){...}
int bar(void){...}
// This guy is INVISIBLE to a.c
int bar22125r51931283(void){...}
int main(void){
   return foo() + bar22125r51931283()
}
```

Functions are `extern` by default at file-scope.

A static-variable must be initialized with a constant expression.
(To make our lives a little easier, our compiler will support only constant
values in initializers, not constant expressions.)

## Static and lifetime

Static in a block means that the little nerd must be referencable forever. It
has a `static` lifetime. (If the compiler can prove that it's not used after a
certain point then yeah it _can_ totally get rid of it, the storage must just be guaranteed)

```c
#include <stdio.h>

int main(void) {
    static int count = 0;
    count = count + 1;
    printf("This function has been called %d times\n", count);
    if (count < 20) {
        main();
    }
    return 0;
}
// This function has been called 1 times
// This function has been called 2 times
// ...
```

```c
int foo(void) {
   static struct VERY_LARGE = { ... };
   do_something();
}

int main(void) {
   foo();
   // safe to delete `VERY_LARGE`
   // But we won't bother with that.
   do_something_else();
}
```

## Extern

Extern means "use some global variable/function provided to us by the linker".

```c
int a = 4; // can be defined in some other file too.

int main(void) {
    int a = 3;
    {
      extern int a;
      // returns 4;
      return a;
    }
}
```

Excellent! But what about this bullshit

```c
// file a.c
int a = 0;
// file b.c
static int a = 12;

int main(void) {
    extern int a;
    return a; // ignores the `extern` thing and just prints 12
}
```

WTH? There's two things going on here:

First of all - it's undefined behaviour lol.

It turns out that if we declare some `extern` thing but that thing was already
declared then we use that things predefined internal linkage.

```c
static int a = 0; // no linkage
extern int a;     // extern? SIKE - undefined behaviour
int b = 0;
extern int b;     // Use the global b (even though b is `static` by default)
// ERROR
extern int c;
static int c = 0;
// clang: Static declaration of 'a' follows non-static declaration
```

The only practical uses for this is stuff like so:

```c
static int my_fun();
#include <something_that_defines_my_fun>
// later on...
int my_fun() {
   // I will ignore the included stuff!
   ;
}
```

## Tentative Definition

```c
int x;

int main(void) {
   return x; // x will be 0
}
```

`tentative` definitions will either be 0 if no other definition is found, or use the second one.
Note: `tentative` is only valid for the same file, otherwise it's undefined behaviour.

```c
int x;

int main(void) {
   return x; // x will be 1
}
int x = 1;
```

Multiple tentative definitions are fine. Behold the madness:

```c
int a;
int a;
extern int a;
int a;
```

If a is defined elsewhere that's an error. Even though we _just_ said that we want it to be extern.

## New Errors

**Conflicting Declarations**

```c
int main() { extern int foo; }

// Static after extern is ILLEGAL
static int foo = 3;

int this_is_also_not_fine() { extern int nope(void); }
static int nope = 2;
```

```c
int foo = 3;

int main(void) {
    // both foo and `foo()` are external, so error
    int foo(void);
    return foo();
}
```

**Restrictions on Storage-Class Specifiers**

You can't apply the extern or static specifier to function parameters or
variables declared in for loop headers. You also can't apply static to function
declarations at block scope. (You can apply extern to them, but it doesn’t do
anything.)

### Linkage and Storage Duration in Assembly

An externaly linkable variable is declared thusly:

```asm
    .globl var # if it has external linkage
    .data
    .align 4
var:
    .long 3
```

Funnily enough the `.align` depends on the OS. On linux this means _"Address must be 4 byte aligned"_.
On Mac it means `2ⁿ` aligned.

**BSS Section** - BSS (Block Started By Symbol) holds static variables that are
initialized to zero, apparently it's a disk-saving thing (an executable just
needs to say how large the BSS section is, not the contents, as they are all zero anyway).

```asm
   .globl var # same as normal `.data`
   .bss
   .align 4
var:
   .zero 4 # size of the `var` in bytes
```

> If a variable is declared, but not defined, in the file you’re compiling, you
> won’t write anything to the data or BSS section.

To reference data in `.data` or `.bss` we use the syntax `var(%rip)` which
refers to memory addresses relative to the instruction pointer.

In case the program is a dynamically linked library then we'd use something
called the _global offset table (GOT)_.
But my compiler is a little baby compiler so I won't be doing any of that.
