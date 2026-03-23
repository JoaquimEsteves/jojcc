# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_12_lexer $(MAKE_CACHE)/chapter_12_lexer: chapter12/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter12/src/chapter12/compiler_driver.py --chapter 12 --stage lex
	touch $(MAKE_CACHE)/chapter_12_lexer
.PHONY: chapter_12_lexer

chapter_12_parser $(MAKE_CACHE)/chapter_12_parser: chapter12/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter12/src/chapter12/compiler_driver.py --chapter 12 --stage parse
	touch $(MAKE_CACHE)/chapter_12_parser
.PHONY: chapter_12_parser

chapter_12_validate $(MAKE_CACHE)/chapter_12_validate: chapter12/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter12/src/chapter12/compiler_driver.py --chapter 12 --stage validate
	touch $(MAKE_CACHE)/chapter_12_validate
.PHONY: chapter_12_validate

chapter_12_tacky $(MAKE_CACHE)/chapter_12_tacky: chapter12/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter12/src/chapter12/compiler_driver.py --chapter 12 --stage tacky
	touch $(MAKE_CACHE)/chapter_12_tacky
.PHONY: chapter_12_tacky

chapter_12_codegen $(MAKE_CACHE)/chapter_12_codegen: chapter12/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter12/src/chapter12/compiler_driver.py --chapter 12 --stage codegen
	touch $(MAKE_CACHE)/chapter_12_codegen
.PHONY: chapter_12_codegen

chapter_12_final $(MAKE_CACHE)/chapter_12_final: chapter12/src/* $(MAKE_CACHE)/chapter_12_pytest | $(MAKE_CACHE)
	$(TEST_PROG) chapter12/src/chapter12/compiler_driver.py --chapter 12
	touch $(MAKE_CACHE)/chapter_12_final
.PHONY: chapter_12_final

chapter_12_pytest $(MAKE_CACHE)/chapter_12_pytest: chapter12/src/* | $(MAKE_CACHE)
	uv run pytest chapter12
	touch $(MAKE_CACHE)/chapter_12_pytest
.PHONY: chapter_12_pytest
