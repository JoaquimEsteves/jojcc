#!/usr/bin/bash
set -euxo pipefail

cd "$(git rev-parse --show-toplevel)" || exit 1

make test
