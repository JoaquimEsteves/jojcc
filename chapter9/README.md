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

### Argument Passing & Cleanup

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

The 7th argument to a function is always at `16(%RBP)`[2], the 8th will depend on the size of the 7th[3].

[2] Recall that at `%RBP` we'll have the the base-pointer of our caller and an
instruction address, both of those are 64 bits, leading to 16 bytes.

[3] Presuming that the 7th argument is an `int32`, then the 8th would be `16 + 32 / 8(%RBP)`, ie `24`.

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
   g,   # STACK[2 * 64 / 8] (ie: 16(%rbp))
   h,   # STACK[2 * 64 / 8 + sizeof(g)] (ie: 24(%rbp))
)
```

Note that we must first push `h` and THEN `g`. The order is reversed.

AFTER the function returns it's the job of the caller to pop any arguments from the stack

```pseudocode
map = { 0: EDI, 1: ESI, ... }
args = [a,b,c...]
for i in args.reversed():
   if i in map:
      yield map[i]
   else:
      yield push_stack(i)
call(func)
for i in args.reversed():
   if i in map:
      pass
   else:
      pop()
```

### Return Values

Return value goes into `EAX` or `RAX` as usual
(The `A` comes from the 1970s convention for _accumulator_)

### Caller-Saved & Callee-Saved Registers

If a register is _caller-saved_, the callee is allowed to overwrite it (So the
caller has to copy it over somewhere if case they want to use it again)
(These registers are `RAX, R10, R11`)

If a register is _callee-saved_ then the callee can't mutate it, it must also be copied.
(All others)

So `caller/callee` tells us which can mutate the value.

`caller-saved` -> `mut`
`callee-saved` -> `const`

EDIT: This previous paragraph feels wrong, I think I misread it.

### Stack Alignment

System V ABI requires the stack to be 16-byte aligned (ie: the address RSP must be divisible by 128 BITS)
Simplest way to do so is to just always align the stack to 16.

(You can inspect the `RSP` and see if it's divisible by `0x10`)

So - if for example we push some 32 int over to the stack we'd need to then push a bunch of extra stuff!

The solution is quite trivial - just ensure that the number of times we push is even.
If it's not - then just subtract some extra padding from the stack.

(Optimizations in the future: Naturally we can just spot that if we want 2 32 bit ints on the stack then
we only need to push it once, but I suppose that is for the future)

### Example

```c
int caller(int arg) {
    return arg + fun(1, 2, 3, 4, 5, 6, 7, 8);
}

int fun(
 int a, # 1
 int b,
 int c,
 int d,
 int e,
 int f, # 6
 int g, # stack
 int h, # stack
) {
    return a + h;
}
```

```asm
    .globl caller
caller:
    # Caller received 1 argument `arg`
    # This will be stored in `EDI`
    # Since we want to remember our `arg` we need to store it on the stack.
    # Note: Whenever we mess with the stack we use quad words.
    # So we push `arg` using `RDI`
    pushq   %rdi
    # fix stack alignment
    subq    $8, %rsp
    # pass first six arguments in registers
    movl    $1, %edi
    movl    $2, %esi
    movl    $3, %edx
    movl    $4, %ecx
    movl    $5, %r8d
    movl    $6, %r9d
    # pass last two arguments on the stack
    pushq   $8
    pushq   $7
    # transfer control to fun
    call    fun
    # restore the stack and RDI
    addq    $24, %rsp    # why 24? See below
    popq    %rdi

    .globl fun
fun:
    pushq   %rbp
    movq    %rsp, %rbp
    # copy first argument into EAX
    movl    %edi, %eax
    # add last argument to EAX
    addl    24(%rbp), %eax
    # epilogue
    movq    %rbp, %rsp
    popq    %rbp
    ret
```

> Why 24?

First we pushed 8 bytes onto the stack. To call `func` we'll also need to push an additional 16 bytes.

So we have: `8 + 8 + 8 == 24`

To align we merely push 8 bytes `24 % 16 = 8`

| Stack Address | Content   | Instruction     |
| ------------- | --------- | --------------- |
| 0             | `arg`     | `pushq %rdi`    |
| 8             | `padding` | `subq $8, %rsp` |
| 16            | `g => 8`  | `pushq $8`      |
| 24            | `h => 7`  | `pushq $7`      |

### The `call` instruction

`call fun` will do a couple of things.

- Pushes the address of the instruction that follows it, the return address, onto the stack
- Copies the label `fun`'s address over to the `Instruction Pointer` (`RIP`)

In effect:

```asm
call fun    # Instruction address: 0x01
one_right_after # instruction address: 0x02 (0x01 + 1)
# same-as (except we can't touch the %RIP directly)
pushq 0x02 %rbp  # So we know where to jump back to!
movl address_of(fun) %rip
```
