# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_9_lexer $(MAKE_CACHE)/chapter_9_lexer: chapter9/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter9/src/chapter9/compiler_driver.py --chapter 9 --stage lex
	touch $(MAKE_CACHE)/chapter_9_lexer
.PHONY: chapter_9_lexer

chapter_9_parser $(MAKE_CACHE)/chapter_9_parser: chapter9/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter9/src/chapter9/compiler_driver.py --chapter 9 --stage parse
	touch $(MAKE_CACHE)/chapter_9_parser
.PHONY: chapter_9_parser

chapter_9_validate $(MAKE_CACHE)/chapter_9_validate: chapter9/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter9/src/chapter9/compiler_driver.py --chapter 9 --stage validate
	touch $(MAKE_CACHE)/chapter_9_validate
.PHONY: chapter_9_validate

chapter_9_tacky $(MAKE_CACHE)/chapter_9_tacky: chapter9/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter9/src/chapter9/compiler_driver.py --chapter 9 --stage tacky
	touch $(MAKE_CACHE)/chapter_9_tacky
.PHONY: chapter_9_tacky

chapter_9_codegen $(MAKE_CACHE)/chapter_9_codegen: chapter9/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter9/src/chapter9/compiler_driver.py --chapter 9 --stage codegen
	touch $(MAKE_CACHE)/chapter_9_codegen
.PHONY: chapter_9_codegen

chapter_9_final $(MAKE_CACHE)/chapter_9_final: chapter9/src/* $(MAKE_CACHE)/chapter_9_pytest | $(MAKE_CACHE)
	$(TEST_PROG) chapter9/src/chapter9/compiler_driver.py --chapter 9
	touch $(MAKE_CACHE)/chapter_9_final
.PHONY: chapter_9_final

chapter_9_pytest $(MAKE_CACHE)/chapter_9_pytest: chapter9/src/* | $(MAKE_CACHE)
	uv run pytest chapter9
	touch $(MAKE_CACHE)/chapter_9_pytest
.PHONY: chapter_9_pytest
