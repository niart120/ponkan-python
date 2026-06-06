#!/bin/sh
set -eu

repo_root=$(git rev-parse --show-toplevel)
cd "$repo_root"

git config core.hooksPath .githooks

printf '%s\n' "Configured core.hooksPath=$(git config --get core.hooksPath)"
