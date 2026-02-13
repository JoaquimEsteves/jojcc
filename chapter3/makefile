# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_3_lexer $(MAKE_CACHE)/chapter_3_lexer: chapter3/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter3/src/chapter3/compiler_driver.py --chapter 3 --stage lex
	touch $(MAKE_CACHE)/chapter_3_lexer
.PHONY: chapter_3_lexer

chapter_3_parser $(MAKE_CACHE)/chapter_3_parser: chapter3/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter3/src/chapter3/compiler_driver.py --chapter 3 --stage parse
	touch $(MAKE_CACHE)/chapter_3_parser
.PHONY: chapter_3_parser

chapter_3_tacky $(MAKE_CACHE)/chapter_3_tacky: chapter3/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter3/src/chapter3/compiler_driver.py --chapter 3 --stage tacky
	touch $(MAKE_CACHE)/chapter_3_tacky
.PHONY: chapter_3_tacky

chapter_3_codegen $(MAKE_CACHE)/chapter_3_codegen: chapter3/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter3/src/chapter3/compiler_driver.py --chapter 3 --stage codegen
	touch $(MAKE_CACHE)/chapter_3_codegen
.PHONY: chapter_3_codegen

chapter_3_final $(MAKE_CACHE)/chapter_3_final: chapter3/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter3/src/chapter3/compiler_driver.py --chapter 3
	touch $(MAKE_CACHE)/chapter_3_final
.PHONY: chapter_3_final
