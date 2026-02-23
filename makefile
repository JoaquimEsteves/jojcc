# TODO(Joaquim): add a `make help`


###############################################################################
#                                    VARS                                     #
###############################################################################

MAKE_CACHE := .make_cache

VENV ?= .venv
# See: https://docs.astral.sh/uv/pip/environments/#using-arbitrary-python-environments

UV_PROJECT_ENVIRONMENT := $(VENV)
# See: https://github.com/astral-sh/uv/issues/7778
# Because the above link is LYING
export UV_PROJECT_ENVIRONMENT 

UV_INSTALLED := $(MAKE_CACHE)/uv_installed  # todo: install uv for the user

TYPE_CHECKER := basedpyright
# Change the type-checker to whichever one you want
# But I prefer basedpyright.

LATEST_ONLY ?= true
FAIL_FAST ?= false
EXTRA_CREDIT ?= true

# Add extra credit later
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

ifeq ($(EXTRA_CREDIT), true)
	# Stop on first failure
	TEST_PROG += --extra-credit
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

type_check:
	$(TYPE_CHECKER) .
.PHONY: type_check

# In `test` mode we always run the final and all previous
test: TEST_PROG=writing-a-c-compiler-tests/test_compiler
test: $(VENV) $(MAKE_CACHE)/chapter_7_final type_check
	@:
.PHONY: test

clean:
	rm -r $(MAKE_CACHE) || true
	rm -r $(VENV)
.PHONY: clean


add_git_hooks: .git/hooks/pre-commit .git/hooks/pre-push
	@:
.PHONY: add_git_hooks


ass:
ifndef F
	$(error Requires the `F=<some_file>.c` arg!)
endif
	$(CC) -S -O -fno-asynchronous-unwind-tables -fcf-protection=none $(F) -o /dev/stdout
.PHONY: ass

debug:
ifndef F
	$(shell echo 1>&2 '$(debug_err_msg)')
	$(error no argument)
endif
ifeq ($(shell command -v ./driver || false),)
	$(shell echo 1>&2 '$(debug_err_msg)')
	$(error no driver)
endif
	cp $(F) debug.c
	./driver -S debug.c > debug.asm
	./driver debug.c
	./debug
.PHONY: debug

new_chapter:
	./scripts/new_chapter.sh
.PHONY: new_chapter

###############################################################################
#                                                                             #
#                                   Targets                                   #
#                                                                             #
###############################################################################


###############################################################################
#                                 Silly vars                                  #
###############################################################################

THIS_TARGET = $@
THIS_PREQ = $?

COLOUR_RED=\033[0;31m
END_COLOUR=\033[0m
COLOUR_YELLOW=\033[0;33m

define debug_err_msg =
$(COLOUR_RED)Error!$(END_COLOUR)\n
This command requires:\n
\n
  * the $(COLOUR_YELLOW)`F=<some_file>.c`$(END_COLOUR) arg\n
  * The $(COLOUR_YELLOW)`driver`$(END_COLOUR), a sym-link to the compiler-driver you want to use\n
\n
Example:\n
\n
```bash\n
$(COLOUR_YELLOW)
ln -sf chapterX/src/chapterX/compiler_driver.py driver\n
make debug F=<your_file>.c\n
$(END_COLOUR)
```

endef

###############################################################################
#                            Non-Python formatter                             #
###############################################################################

$(MAKE_CACHE)/Formatted_%.md: %.md
ifeq ($(shell command -v prettier || false),)
	$(info Could not format markdown files! Download prettier)
else
	prettier --write $(THIS_PREQ)
endif
	mkdir -p $(dir $(THIS_TARGET))
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
include chapter5/makefile
include chapter6/makefile
include chapter7/makefile
