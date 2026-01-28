COMPILER ?= gcc

see_ass return_2.s: return_2.c
	$(COMPILER) -S -O -fno-asynchronous-unwind-tables -fcf-protection=none return_2.c
	cat return_2.s
.PHONY: see_ass
