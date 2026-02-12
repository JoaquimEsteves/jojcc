# This file is not meant to be used directly.
# It's instead included by the top-level makefile

chapter_5_lexer $(MAKE_CACHE)/chapter_5_lexer: chapter5/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter5/src/chapter5/compiler_driver.py --chapter 5 --stage lex --bitwise
	touch $(MAKE_CACHE)/chapter_5_lexer
.PHONY: chapter_5_lexer

chapter_5_parser $(MAKE_CACHE)/chapter_5_parser: chapter5/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter5/src/chapter5/compiler_driver.py --chapter 5 --stage parse  --bitwise
	touch $(MAKE_CACHE)/chapter_5_parser
.PHONY: chapter_5_parser

chapter_5_validate $(MAKE_CACHE)/chapter_5_validate: chapter5/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter5/src/chapter5/compiler_driver.py --chapter 5 --stage validate --bitwise
	touch $(MAKE_CACHE)/chapter_5_validate
.PHONY: chapter_5_validate

chapter_5_tacky $(MAKE_CACHE)/chapter_5_tacky: chapter5/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter5/src/chapter5/compiler_driver.py --chapter 5 --stage tacky --bitwise
	touch $(MAKE_CACHE)/chapter_5_tacky
.PHONY: chapter_5_tacky

chapter_5_codegen $(MAKE_CACHE)/chapter_5_codegen: chapter5/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter5/src/chapter5/compiler_driver.py --chapter 5 --stage codegen --bitwise
	touch $(MAKE_CACHE)/chapter_5_codegen
.PHONY: chapter_5_codegen

chapter_5_final $(MAKE_CACHE)/chapter_5_final: chapter5/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter5/src/chapter5/compiler_driver.py --chapter 5 --bitwise
	touch $(MAKE_CACHE)/chapter_5_final
.PHONY: chapter_5_final
