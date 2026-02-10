#!/usr/bin/env bash

set -euxo pipefail

cd "$(git rev-parse --show-toplevel)"

# How the heck could I do this in bash?
# Probably possible, but I don't care to find out
python_code='
import re
from glob import glob

def check(s):
    return int(re.match(r"chapter(\d+)", s).groups()[0])

print(max(map(check, glob("chapter*"))))
'

latest_chapter=$(python3 -c "$python_code")
next_chapter=$((latest_chapter + 1))

cp -r "chapter$latest_chapter" "chapter$next_chapter"
mv "chapter$next_chapter/src/chapter$latest_chapter" "chapter$next_chapter/src/chapter$next_chapter"

cd chapter$next_chapter

function replace(){
   command grep "$1" -r . -l | xargs sed -i "s#$2#$3#g"
}

replace "chapter $latest_chapter" "chapter $latest_chapter" "chapter $next_chapter"
replace "chapter_$latest_chapter" "chapter_$latest_chapter" "chapter_$next_chapter"
replace "chapter$latest_chapter" "chapter$latest_chapter" "chapter$next_chapter"

cd "$(git rev-parse --show-toplevel)"

uv add --workspace "./chapter$next_chapter"
