# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_7_lexer $(MAKE_CACHE)/chapter_7_lexer: chapter7/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter7/src/chapter7/compiler_driver.py --chapter 7 --stage lex
	touch $(MAKE_CACHE)/chapter_7_lexer
.PHONY: chapter_7_lexer

chapter_7_parser $(MAKE_CACHE)/chapter_7_parser: chapter7/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter7/src/chapter7/compiler_driver.py --chapter 7 --stage parse
	touch $(MAKE_CACHE)/chapter_7_parser
.PHONY: chapter_7_parser

chapter_7_validate $(MAKE_CACHE)/chapter_7_validate: chapter7/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter7/src/chapter7/compiler_driver.py --chapter 7 --stage validate
	touch $(MAKE_CACHE)/chapter_7_validate
.PHONY: chapter_7_validate

chapter_7_tacky $(MAKE_CACHE)/chapter_7_tacky: chapter7/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter7/src/chapter7/compiler_driver.py --chapter 7 --stage tacky
	touch $(MAKE_CACHE)/chapter_7_tacky
.PHONY: chapter_7_tacky

chapter_7_codegen $(MAKE_CACHE)/chapter_7_codegen: chapter7/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter7/src/chapter7/compiler_driver.py --chapter 7 --stage codegen
	touch $(MAKE_CACHE)/chapter_7_codegen
.PHONY: chapter_7_codegen

chapter_7_final $(MAKE_CACHE)/chapter_7_final: chapter7/src/* $(MAKE_CACHE)/chapter_7_pytest | $(MAKE_CACHE)
	$(TEST_PROG) chapter7/src/chapter7/compiler_driver.py --chapter 7
	touch $(MAKE_CACHE)/chapter_7_final
.PHONY: chapter_7_final

chapter_7_pytest $(MAKE_CACHE)/chapter_7_pytest: chapter7/src/* | $(MAKE_CACHE)
	uv run pytest chapter7
	touch $(MAKE_CACHE)/chapter_7_pytest
.PHONY: chapter_7_pytest
