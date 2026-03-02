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
┌──▼────────────────────┐
│Semantic Analysis      │
│╔═════════════════════╗│
│║Identifier Resolution║│ <- Renamed Shit!
│╚═════════════════════╝│
│╔═════════════════════╗│
│║    Type Checking    ║│<- New shit!
│╚═════════════════════╝│
│╔═════════════════════╗│
│║   Loop Labelling    ║│
│╚═════════════════════╝│
└──┬────────────────────┘
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

Of note for my little compiler is that I should _NOT_ rename things that are meant for external linkage.
So for now - that means that functions _SHOULD NOT_ get their name changed.

### Calling Convention and ABI

ABI -> All Unix systems use a standard calling convention defined in the System V ABI[1].
Of course this silly ABI changes depending on the architecture of the
processor, but the book doesn't care and just assumes x64 processors.

A part of the ABI is the calling convention, said calling convention is a
contract that explains the following:

> - How are arguments passed to the callee? Are they passed in registers or on
>   the stack?
> - How is a function’s return value passed back to the caller?
> - Is the callee or caller responsible for removing arguments from the stack
>   at the end of a function?
> - Which registers is the callee allowed to overwrite, and which does it need
>   to preserve?

[1]: System 5 came from Unix System 5, one of those old commercial Unixes

### Argument Passing

The first 6 integer arguments to a function are passed through special registers.

| #   | Register 32 | Register 64 |
| --- | ----------- | ----------- |
| 0   | EDI         | RDI         |
| 1   | ESI         | RSI         |
| 2   | EDX         | RDX         |
| 3   | ECX         | RCX         |
| 4   | R8D         | R8          |
| 5   | R9D         | R9          |

Stuff that doesn't fit will then be shunted off to some pointer.
If a function has more than 6 arguments, those are simply pushed to the stack.

Note that the name these registers have is very tricky to memorize, I hate it!
Here's [an article that goes into detail](https://keleshev.com/eax-x86-register-meaning-and-history/).
Companion [hacker news discussion](https://news.ycombinator.com/item?id=22645910)

Example:

```
f(
   a,   # EDI
   b,   # ESI
   c,   # EDX
   d,   # ECX
   e,   # R8D
   f,   # R9D
   g,   # STACK[1]
   h,   # STACK[0]
)
```

Note that we must first push `h` and THEN `g`. The order is reversed.

```pseudocode
map = { 0: EDI, 1: ESI, ... }
args = [a,b,c...]
for i in args.reversed():
   if i in map:
      yield map[i]
   else:
      yield push_stack(i)
```

Return value goes into `EAX` or `RAX` as usual
(The `A` comes from the 1970s convention for _accumulator_)
