# TODO(Joaquim):
# add a `make help`

MAKE_CACHE := .make_cache
HAS_INSTALLED := $(MAKE_CACHE)/has_installed
UV_INSTALLED := $(MAKE_CACHE)/uv_installed
# If you're using the `uv` based pyright feel free to tweak it here
PYRIGHT := basedpyright

TEST_PROG := writing-a-c-compiler-tests/test_compiler

install $(HAS_INSTALLED): pyproject.toml | $(MAKE_CACHE) .git/hooks/pre-commit .git/hooks/pre-push
	uv sync
	touch $(HAS_INSTALLED)
.PHONY: install

lint: $(HAS_INSTALLED)
	uv run ruff check
	uv run ruff format --check
.PHONY: lint

format: $(HAS_INSTALLED)
	uv run ruff format
.PHONY: format

test: $(HAS_INSTALLED) $(MAKE_CACHE)/chapter_1_lexer $(MAKE_CACHE)/chapter_1_parser
	$(PYRIGHT) .
.PHONY: test

clean:
	rm -r $(MAKE_CACHE) || true
	rm -r .venv
.PHONY: clean


chapter_1_lexer $(MAKE_CACHE)/chapter_1_lexer: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1 --stage lex
	touch $(MAKE_CACHE)/chapter_1_lexer
.PHONY: chapter_1_lexer

chapter_1_parser $(MAKE_CACHE)/chapter_1_parser: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1 --stage parse
	touch $(MAKE_CACHE)/chapter_1_parser
.PHONY: chapter_1_parser

chapter_1_codegen $(MAKE_CACHE)/chapter_1_codegen: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1 --stage codegen
	touch $(MAKE_CACHE)/chapter_1_codegen
.PHONY: chapter_1_codegen

chapter_1_final $(MAKE_CACHE)/chapter_1_final: chapter1/src/* | $(MAKE_CACHE)
	$(TEST_PROG) chapter1/src/chapter1/compiler_driver.py --chapter 1
	touch $(MAKE_CACHE)/chapter_1_final
.PHONY: chapter_1_final

.git/hooks/pre-commit:
	ln -sf $(realpath scripts/pre_commit.sh) .git/hooks/pre-commit

.git/hooks/pre-push:
	ln -sf $(realpath scripts/pre_push.sh) .git/hooks/pre-push

add_git_hooks: .git/hooks/pre-commit .git/hooks/pre-push
	@:
.PHONY: add_git_hooks

$(MAKE_CACHE):
	mkdir --parents $(MAKE_CACHE)
