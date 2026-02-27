# Chapter 9: FUNCTIONS BABY

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
└──┬────┘
┌──▼───────────────────┐
│Semantic Analysis     │
│╔═══════════════════╗ │
│║Variable Resolution║ │
│╚═══════════════════╝ │
│╔═══════════════════╗ │
│║   Type Checking   ║ │ <- New shit!
│╚═══════════════════╝ │
│╔═══════════════════╗ │
│║  Loop Labelling   ║ │
│╚═══════════════════╝ │
└──┬───────────────────┘
   │
   │  AST
   │
 ┌─▼──────────────┐
 │TACKY GENERATION│
 └─┬──────────────┘
   │
┌──▼──────────────────────────────────┐
│ Assembly Generation                 │
│ ╔═════════════════════════════╗     │
│ ║Converting TACKY to assembly ║     │
│ ╚═════════════════════════════╝     │
│ ╔═════════════════════════════╗     │
│ ║  Replacing pseudoregisters  ║     │
│ ╚═════════════════════════════╝     │
│ ╔═════════════════════════════╗     │
│ ║    Instruction fix-up       ║     │
│ ╚═════════════════════════════╝     │
└──┬──────────────────────────────────┘
   │  Assembly
   │
┌──▼──────────┐
│Code Emission│
└──┬──────────┘
   ▼
program.s
```

🗣️ WE GONNA BE ABLE TO DO IO BABY 🗣️

## TIL

- You can declare functions inside the body of other functions??? WHAT?

```c
int main(void) {
    // perfectly valid C apparently
    int foo(int a, int b);
    return foo(1, 2);
}
```

Supposedly this is to that functions can shadow variable names.

```c
int main(void) {
   int printf = 5;
   if (printf > 1) {
      int printf(const char *, ...);
      printf("XD\n");
      // in a sane language this would be
      // printf := include('stdio').printf
   }
}
```

Note that the declared function _must_ have a non-conflicting type.

```c
int foo(int, int);
int foo(int arg1, int arg2);
int foo(int weirdly_enough, int not_a_problem);
int foo(int this, int will, int cause, int an_error);
```

- C allows you to define functions like so:

```c
int foo(param1, param2, param3)
int param1, param2, param3;
{
    return param1 + param2 + param3;
}
```

The book tells us not to bother doing things this way, indeed `clang` helpfully
informs us that this is deprecated:

> A function definition without a prototype is deprecated in all versions of C
> and is not supported in C23 [-Wdeprecated-non-prototype]

The C standard defines certain "features" as `obsolete`. They _might_ or might
not be removed in later versions of the standard.

- The following jank syntax:

```c
int foo();
```

Has a different meaning depending on the C-standard used!
In `<=C17` it means _"The function can have however many parameters you feel like bro"_.
In `C23>=` instead if means `foo(void)`.

> According to the C17 standard, a function declaration without a parameter
> list or function body provides no information about that function’s
> parameters. In other words, this declaration indicates that some function foo
> is in scope and returns an integer, but it doesn't tell us how many
> parameters it has. Empty parameter lists are also obsolescent in C17. In C23,
> they’re permitted, but their meaning has changed: instead of declaring a
> function without specifying its parameters, an empty parameter list declares
> a function with no parameters. In other words, the declarations int foo();
> and int foo(void); are equivalent in C23.

- It's ILLEGAL to call a function before it's defined

```c
int main(void) {
    return foo(1, 2, 3);
}

int foo(int arg1, int arg2, int arg3);
```

So `includes` and stuff _have_ to go on top.

- External vs Internal Linkage

Pretty simple, in the assembly file if the linker sees:

```asm
	.globl whatever
whatever:
```

Then other object files can use that `whatever`. If two object files have a
`.global whatever` then linkage fails.
Internal linkage just means that we can define the same reference multiple times with the same name, but
other object files can't reference the same thing.
