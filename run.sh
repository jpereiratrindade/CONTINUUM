#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
exec python3 -m lab --db "${LAB_DB:-./data/continuum.sqlite}" --workspace "${LAB_WORKSPACE:-./workspace}" serve "${@}"
