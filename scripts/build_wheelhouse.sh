#!/usr/bin/env bash
set -euo pipefail

# Build the committed offline wheelhouse for the air-gapped server.
#
# Target: Linux x86_64, CPython 3.12 (matches the server). Run this on ANY
# machine with internet access (the wheels are cross-downloaded, so it works
# from macOS too), then commit the refreshed wheelhouse/.
#
# Usage:
#   scripts/build_wheelhouse.sh
#
# Override the target if the server ever changes:
#   PYTHON_VERSION=3.12 ABI_TAG=cp312 scripts/build_wheelhouse.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ_FILE="${ROOT_DIR}/requirements.txt"
OUT_DIR="${ROOT_DIR}/wheelhouse"

PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
IMPLEMENTATION="${IMPLEMENTATION:-cp}"
ABI_TAG="${ABI_TAG:-cp312}"

rm -rf "${OUT_DIR}"
mkdir -p "${OUT_DIR}"

# Multiple manylinux tags so modern numpy/pandas wheels (glibc >= 2.24/2.27)
# resolve correctly, not just the old manylinux2014 (glibc 2.17).
python3 -m pip download \
  --requirement "${REQ_FILE}" \
  --dest "${OUT_DIR}" \
  --only-binary=:all: \
  --implementation "${IMPLEMENTATION}" \
  --python-version "${PYTHON_VERSION}" \
  --abi "${ABI_TAG}" \
  --platform manylinux2014_x86_64 \
  --platform manylinux_2_17_x86_64 \
  --platform manylinux_2_28_x86_64

echo "Wheelhouse refreshed at: ${OUT_DIR}"
echo "Commit it so the offline server gets the wheels via git."
