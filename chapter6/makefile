# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_6_lexer $(MAKE_CACHE)/chapter_6_lexer: chapter6/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter6/src/chapter6/compiler_driver.py --chapter 6 --stage lex
	touch $(MAKE_CACHE)/chapter_6_lexer
.PHONY: chapter_6_lexer

chapter_6_parser $(MAKE_CACHE)/chapter_6_parser: chapter6/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter6/src/chapter6/compiler_driver.py --chapter 6 --stage parse
	touch $(MAKE_CACHE)/chapter_6_parser
.PHONY: chapter_6_parser

chapter_6_validate $(MAKE_CACHE)/chapter_6_validate: chapter6/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter6/src/chapter6/compiler_driver.py --chapter 6 --stage validate
	touch $(MAKE_CACHE)/chapter_6_validate
.PHONY: chapter_6_validate

chapter_6_tacky $(MAKE_CACHE)/chapter_6_tacky: chapter6/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter6/src/chapter6/compiler_driver.py --chapter 6 --stage tacky
	touch $(MAKE_CACHE)/chapter_6_tacky
.PHONY: chapter_6_tacky

chapter_6_codegen $(MAKE_CACHE)/chapter_6_codegen: chapter6/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter6/src/chapter6/compiler_driver.py --chapter 6 --stage codegen
	touch $(MAKE_CACHE)/chapter_6_codegen
.PHONY: chapter_6_codegen

chapter_6_final $(MAKE_CACHE)/chapter_6_final: chapter6/src/* $(MAKE_CACHE)/chapter_6_pytest | $(MAKE_CACHE)
	$(TEST_PROG) chapter6/src/chapter6/compiler_driver.py --chapter 6
	touch $(MAKE_CACHE)/chapter_6_final
.PHONY: chapter_6_final

chapter_6_pytest $(MAKE_CACHE)/chapter_6_pytest: chapter6/src/* | $(MAKE_CACHE)
	uv run pytest chapter6
	touch $(MAKE_CACHE)/chapter_6_pytest
.PHONY: chapter_6_pytest
