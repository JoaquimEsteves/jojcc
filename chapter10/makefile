# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_10_lexer $(MAKE_CACHE)/chapter_10_lexer: chapter10/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter10/src/chapter10/compiler_driver.py --chapter 10 --stage lex
	touch $(MAKE_CACHE)/chapter_10_lexer
.PHONY: chapter_10_lexer

chapter_10_parser $(MAKE_CACHE)/chapter_10_parser: chapter10/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter10/src/chapter10/compiler_driver.py --chapter 10 --stage parse
	touch $(MAKE_CACHE)/chapter_10_parser
.PHONY: chapter_10_parser

chapter_10_validate $(MAKE_CACHE)/chapter_10_validate: chapter10/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter10/src/chapter10/compiler_driver.py --chapter 10 --stage validate
	touch $(MAKE_CACHE)/chapter_10_validate
.PHONY: chapter_10_validate

chapter_10_tacky $(MAKE_CACHE)/chapter_10_tacky: chapter10/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter10/src/chapter10/compiler_driver.py --chapter 10 --stage tacky
	touch $(MAKE_CACHE)/chapter_10_tacky
.PHONY: chapter_10_tacky

chapter_10_codegen $(MAKE_CACHE)/chapter_10_codegen: chapter10/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter10/src/chapter10/compiler_driver.py --chapter 10 --stage codegen
	touch $(MAKE_CACHE)/chapter_10_codegen
.PHONY: chapter_10_codegen

chapter_10_final $(MAKE_CACHE)/chapter_10_final: chapter10/src/* $(MAKE_CACHE)/chapter_10_pytest | $(MAKE_CACHE)
	$(TEST_PROG) chapter10/src/chapter10/compiler_driver.py --chapter 10
	touch $(MAKE_CACHE)/chapter_10_final
.PHONY: chapter_10_final

chapter_10_pytest $(MAKE_CACHE)/chapter_10_pytest: chapter10/src/* | $(MAKE_CACHE)
	uv run pytest chapter10
	touch $(MAKE_CACHE)/chapter_10_pytest
.PHONY: chapter_10_pytest
