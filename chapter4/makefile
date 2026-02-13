# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_4_lexer $(MAKE_CACHE)/chapter_4_lexer: chapter4/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter4/src/chapter4/compiler_driver.py --chapter 4 --stage lex
	touch $(MAKE_CACHE)/chapter_4_lexer
.PHONY: chapter_4_lexer

chapter_4_parser $(MAKE_CACHE)/chapter_4_parser: chapter4/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter4/src/chapter4/compiler_driver.py --chapter 4 --stage parse
	touch $(MAKE_CACHE)/chapter_4_parser
.PHONY: chapter_4_parser

chapter_4_tacky $(MAKE_CACHE)/chapter_4_tacky: chapter4/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter4/src/chapter4/compiler_driver.py --chapter 4 --stage tacky
	touch $(MAKE_CACHE)/chapter_4_tacky
.PHONY: chapter_4_tacky

chapter_4_codegen $(MAKE_CACHE)/chapter_4_codegen: chapter4/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter4/src/chapter4/compiler_driver.py --chapter 4 --stage codegen
	touch $(MAKE_CACHE)/chapter_4_codegen
.PHONY: chapter_4_codegen

chapter_4_final $(MAKE_CACHE)/chapter_4_final: chapter4/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter4/src/chapter4/compiler_driver.py --chapter 4
	touch $(MAKE_CACHE)/chapter_4_final
.PHONY: chapter_4_final
