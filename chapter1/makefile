# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_1_lexer $(MAKE_CACHE)/chapter_1_lexer: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1 --stage lex
	touch $(MAKE_CACHE)/chapter_1_lexer
.PHONY: chapter_1_lexer

chapter_1_parser $(MAKE_CACHE)/chapter_1_parser: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1 --stage parse
	touch $(MAKE_CACHE)/chapter_1_parser
.PHONY: chapter_1_parser

chapter_1_codegen $(MAKE_CACHE)/chapter_1_codegen: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1 --stage codegen
	touch $(MAKE_CACHE)/chapter_1_codegen
.PHONY: chapter_1_codegen

chapter_1_final $(MAKE_CACHE)/chapter_1_final: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1
	touch $(MAKE_CACHE)/chapter_1_final
.PHONY: chapter_1_final
