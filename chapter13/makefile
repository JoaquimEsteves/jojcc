# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_13_lexer $(MAKE_CACHE)/chapter_13_lexer: chapter13/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter13/src/chapter13/compiler_driver.py --chapter 13 --stage lex
	touch $(MAKE_CACHE)/chapter_13_lexer
.PHONY: chapter_13_lexer

chapter_13_parser $(MAKE_CACHE)/chapter_13_parser: chapter13/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter13/src/chapter13/compiler_driver.py --chapter 13 --stage parse
	touch $(MAKE_CACHE)/chapter_13_parser
.PHONY: chapter_13_parser

chapter_13_validate $(MAKE_CACHE)/chapter_13_validate: chapter13/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter13/src/chapter13/compiler_driver.py --chapter 13 --stage validate
	touch $(MAKE_CACHE)/chapter_13_validate
.PHONY: chapter_13_validate

chapter_13_tacky $(MAKE_CACHE)/chapter_13_tacky: chapter13/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter13/src/chapter13/compiler_driver.py --chapter 13 --stage tacky
	touch $(MAKE_CACHE)/chapter_13_tacky
.PHONY: chapter_13_tacky

chapter_13_codegen $(MAKE_CACHE)/chapter_13_codegen: chapter13/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter13/src/chapter13/compiler_driver.py --chapter 13 --stage codegen
	touch $(MAKE_CACHE)/chapter_13_codegen
.PHONY: chapter_13_codegen

chapter_13_final $(MAKE_CACHE)/chapter_13_final: chapter13/src/* $(MAKE_CACHE)/chapter_13_pytest | $(MAKE_CACHE)
	$(TEST_PROG) chapter13/src/chapter13/compiler_driver.py --chapter 13
	touch $(MAKE_CACHE)/chapter_13_final
.PHONY: chapter_13_final

chapter_13_pytest $(MAKE_CACHE)/chapter_13_pytest: chapter13/src/* | $(MAKE_CACHE)
	uv run pytest chapter13
	touch $(MAKE_CACHE)/chapter_13_pytest
.PHONY: chapter_13_pytest
