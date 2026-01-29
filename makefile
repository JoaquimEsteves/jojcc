# TODO(Joaquim):
# add a `make help`
# also add a `test` script?
# Add the usual make-crap defaults

MAKE_CACHE := .make_cache
HAS_INSTALLED := $(MAKE_CACHE)/has_installed
UV_INSTALLED := $(MAKE_CACHE)/uv_installed
# If you're using the `uv` based pyright feel free to tweak it here
PYRIGHT := basedpyright

TEST_PROG := writing-a-c-compiler-tests/test_compiler

lint: $(HAS_INSTALLED)
	uv run ruff check
	uv run ruff format --check
.PHONY: lint


test: $(HAS_INSTALLED) $(MAKE_CACHE)/chapter_1_lexer $(MAKE_CACHE)/chapter_1_parser
	$(PYRIGHT) .
.PHONY: test


chapter_1_lexer $(MAKE_CACHE)/chapter_1_lexer: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1 --stage lex
	touch $(MAKE_CACHE)/chapter_1_lexer
.PHONY: chapter_1_lexer

chapter_1_parser $(MAKE_CACHE)/chapter_1_parser: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1 --stage parse
	touch $(MAKE_CACHE)/chapter_1_parser
.PHONY: chapter_1_lexer

format: $(HAS_INSTALLED)
	uv run ruff format
.PHONY: format

install $(HAS_INSTALLED): | $(MAKE_CACHE)
	uv sync
	touch $(HAS_INSTALLED)
.PHONY: install

clean:
	rm -r $(MAKE_CACHE) || true
	rm -r .venv
.PHONY: clean


$(MAKE_CACHE):
	mkdir --parents $(MAKE_CACHE)
