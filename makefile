# TODO(Joaquim): add a `make help`


###############################################################################
#                                    VARS                                     #
###############################################################################

MAKE_CACHE := .make_cache

# See: https://docs.astral.sh/uv/pip/environments/#using-arbitrary-python-environments
VENV ?= .venv
# See: https://github.com/astral-sh/uv/issues/7778
UV_PROJECT_ENVIRONMENT := $(VENV)
export UV_PROJECT_ENVIRONMENT 

UV_INSTALLED := $(MAKE_CACHE)/uv_installed
# If you're using the `uv` based pyright feel free to tweak it here
PYRIGHT := basedpyright

LATEST_ONLY ?= true
FAIL_FAST ?= false

TEST_PROG := writing-a-c-compiler-tests/test_compiler

ifeq ($(LATEST_ONLY), true)
	# --latest-only only checks the stuff for one particular chapter
	#  Generally that's what we want
	TEST_PROG += --latest-only
endif

ifeq ($(FAIL_FAST), true)
	# Stop on first failure
	TEST_PROG += --failfast
endif


###############################################################################
#                                  Commands                                   #
###############################################################################

install $(VENV): pyproject.toml | $(MAKE_CACHE) .git/hooks/pre-commit .git/hooks/pre-push
	uv sync
	touch $(UV_PROJECT_ENVIRONMENT)
.PHONY: install


MARKDOWN_FILES := $(shell git ls-files '*.md') 
FORMATTED_MARKDOWN := $(addprefix $(MAKE_CACHE)/Formatted_, $(MARKDOWN_FILES))

lint: $(VENV) $(FORMATTED_MARKDOWN) | $(MAKE_CACHE)
	uv run ruff check
	uv run ruff format --check
.PHONY: lint

format: $(VENV) $(FORMATTED_MARKDOWN) | $(MAKE_CACHE)
	uv run ruff format
.PHONY: format

# In `test` mode we always run the final and all previous
test: TEST_PROG=writing-a-c-compiler-tests/test_compiler
test: $(VENV) $(MAKE_CACHE)/chapter_4_final | $(MAKE_CACHE)
	$(PYRIGHT) .
.PHONY: test

clean:
	rm -r $(MAKE_CACHE) || true
	rm -r $(VENV)
.PHONY: clean


add_git_hooks: .git/hooks/pre-commit .git/hooks/pre-push
	@:
.PHONY: add_git_hooks


###############################################################################
#                                                                             #
#                                   Targets                                   #
#                                                                             #
###############################################################################

THIS_TARGET = $@
THIS_PREQ = $?

###############################################################################
#                            Non-Python formatter                             #
###############################################################################
HAS_PRETTIER := $(shell command -v prettier || false)

$(MAKE_CACHE)/Formatted_%.md: %.md

ifndef HAS_PRETTIER
	$(info Could not format markdown files! Download prettier)
else
	prettier --write $(THIS_PREQ)
	mkdir -p $(dir $(THIS_TARGET))
endif
	touch $(THIS_TARGET)


###############################################################################
#                                  Git-Hooks                                  #
###############################################################################
.git/hooks/pre-commit:
	ln -sf $(realpath scripts/pre_commit.sh) .git/hooks/pre-commit

.git/hooks/pre-push:
	ln -sf $(realpath scripts/pre_push.sh) .git/hooks/pre-push


$(MAKE_CACHE):
	mkdir --parents $(MAKE_CACHE)

###############################################################################
#                                  Includes                                   #
###############################################################################
include chapter1/makefile
include chapter2/makefile
include chapter3/makefile
include chapter4/makefile
