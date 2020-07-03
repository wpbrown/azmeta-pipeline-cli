#!/bin/bash
set -ex

DEST_DIR="build"
mkdir -p "${DEST_DIR}"
shiv -r "requirements.txt" --no-deps . -o "build/azmpcli.pyz" -e azmpcli.__main__:cli -p "/opt/az/bin/python3"