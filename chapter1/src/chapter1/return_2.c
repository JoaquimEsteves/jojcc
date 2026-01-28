//usr/bin/gcc "$0" && exec ./a.out "$@"
// Compile with `$ gcc -S -O -fno-asynchronous-unwind-tables -fcf-protection=none return_2.c`
// -S: Emit the assembly, by not running the assembler or linker
// -O optimize to clean up some instructions
// namely:
//        ✂️  pushq   %rbp
//        ✂️  movq    %rsp, %rbp
//        movl    $2, %eax
//        ✂️  popq    %rbp
// -fno-asynchronous-unwind-tables Don’t generate the unwind table, which is
// used for debugging. We don’t need it.
//
// -fcf-protection=none Disable control-flow protection, a security feature
// that adds extra instructions we aren’t concerned with. Control-flow
// protection might already be disabled by default on your system, in which
// case this option won’t do anything.

int main(void) { return 2; }
