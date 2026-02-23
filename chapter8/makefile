# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_8_lexer $(MAKE_CACHE)/chapter_8_lexer: chapter8/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter8/src/chapter8/compiler_driver.py --chapter 8 --stage lex
	touch $(MAKE_CACHE)/chapter_8_lexer
.PHONY: chapter_8_lexer

chapter_8_parser $(MAKE_CACHE)/chapter_8_parser: chapter8/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter8/src/chapter8/compiler_driver.py --chapter 8 --stage parse
	touch $(MAKE_CACHE)/chapter_8_parser
.PHONY: chapter_8_parser

chapter_8_validate $(MAKE_CACHE)/chapter_8_validate: chapter8/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter8/src/chapter8/compiler_driver.py --chapter 8 --stage validate
	touch $(MAKE_CACHE)/chapter_8_validate
.PHONY: chapter_8_validate

chapter_8_tacky $(MAKE_CACHE)/chapter_8_tacky: chapter8/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter8/src/chapter8/compiler_driver.py --chapter 8 --stage tacky
	touch $(MAKE_CACHE)/chapter_8_tacky
.PHONY: chapter_8_tacky

chapter_8_codegen $(MAKE_CACHE)/chapter_8_codegen: chapter8/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter8/src/chapter8/compiler_driver.py --chapter 8 --stage codegen
	touch $(MAKE_CACHE)/chapter_8_codegen
.PHONY: chapter_8_codegen

chapter_8_final $(MAKE_CACHE)/chapter_8_final: chapter8/src/* $(MAKE_CACHE)/chapter_8_pytest | $(MAKE_CACHE)
	$(TEST_PROG) chapter8/src/chapter8/compiler_driver.py --chapter 8
	touch $(MAKE_CACHE)/chapter_8_final
.PHONY: chapter_8_final

chapter_8_pytest $(MAKE_CACHE)/chapter_8_pytest: chapter8/src/* | $(MAKE_CACHE)
	uv run pytest chapter8
	touch $(MAKE_CACHE)/chapter_8_pytest
.PHONY: chapter_8_pytest
