COMPILER ?= gcc

see_ass return_2.s: src/chapter1/return_2.c
	$(COMPILER) -S -O -fno-asynchronous-unwind-tables -fcf-protection=none src/chapter1/return_2.c
	cat return_2.s
.PHONY: see_ass
