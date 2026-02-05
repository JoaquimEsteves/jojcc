# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_2_lexer $(MAKE_CACHE)/chapter_2_lexer: chapter2/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter2/src/chapter2/compiler_driver.py --chapter 2 --stage lex
	touch $(MAKE_CACHE)/chapter_2_lexer
.PHONY: chapter_2_lexer

chapter_2_parser $(MAKE_CACHE)/chapter_2_parser: chapter2/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter2/src/chapter2/compiler_driver.py --chapter 2 --stage parse
	touch $(MAKE_CACHE)/chapter_2_parser
.PHONY: chapter_2_parser

chapter_2_tacky $(MAKE_CACHE)/chapter_2_tacky: chapter2/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter2/src/chapter2/compiler_driver.py --chapter 2 --stage tacky
	touch $(MAKE_CACHE)/chapter_2_tacky
.PHONY: chapter_2_tacky

chapter_2_codegen $(MAKE_CACHE)/chapter_2_codegen: chapter2/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter2/src/chapter2/compiler_driver.py --chapter 2 --stage codegen
	touch $(MAKE_CACHE)/chapter_2_codegen
.PHONY: chapter_2_codegen

chapter_2_final $(MAKE_CACHE)/chapter_2_final: chapter2/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter2/src/chapter2/compiler_driver.py --chapter 2
	touch $(MAKE_CACHE)/chapter_2_final
.PHONY: chapter_2_final
