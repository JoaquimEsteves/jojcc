# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_11_lexer $(MAKE_CACHE)/chapter_11_lexer: chapter11/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter11/src/chapter11/compiler_driver.py --chapter 11 --stage lex
	touch $(MAKE_CACHE)/chapter_11_lexer
.PHONY: chapter_11_lexer

chapter_11_parser $(MAKE_CACHE)/chapter_11_parser: chapter11/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter11/src/chapter11/compiler_driver.py --chapter 11 --stage parse
	touch $(MAKE_CACHE)/chapter_11_parser
.PHONY: chapter_11_parser

chapter_11_validate $(MAKE_CACHE)/chapter_11_validate: chapter11/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter11/src/chapter11/compiler_driver.py --chapter 11 --stage validate
	touch $(MAKE_CACHE)/chapter_11_validate
.PHONY: chapter_11_validate

chapter_11_tacky $(MAKE_CACHE)/chapter_11_tacky: chapter11/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter11/src/chapter11/compiler_driver.py --chapter 11 --stage tacky
	touch $(MAKE_CACHE)/chapter_11_tacky
.PHONY: chapter_11_tacky

chapter_11_codegen $(MAKE_CACHE)/chapter_11_codegen: chapter11/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter11/src/chapter11/compiler_driver.py --chapter 11 --stage codegen
	touch $(MAKE_CACHE)/chapter_11_codegen
.PHONY: chapter_11_codegen

chapter_11_final $(MAKE_CACHE)/chapter_11_final: chapter11/src/* $(MAKE_CACHE)/chapter_11_pytest | $(MAKE_CACHE)
	$(TEST_PROG) chapter11/src/chapter11/compiler_driver.py --chapter 11
	touch $(MAKE_CACHE)/chapter_11_final
.PHONY: chapter_11_final

chapter_11_pytest $(MAKE_CACHE)/chapter_11_pytest: chapter11/src/* | $(MAKE_CACHE)
	uv run pytest chapter11
	touch $(MAKE_CACHE)/chapter_11_pytest
.PHONY: chapter_11_pytest
