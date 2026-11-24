#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="${ROOT_DIR}/rust/manic_fitter/Cargo.toml"
DEST_DIR="${ROOT_DIR}/src/manic/processors"

cargo build --release --manifest-path "${MANIFEST}"

case "$(uname -s)" in
    Darwin) LIB_NAME="libmanic_fitter.dylib" ;;
    Linux)  LIB_NAME="libmanic_fitter.so" ;;
    *)      echo "Unsupported Unix platform: $(uname -s)" >&2; exit 1 ;;
esac

SRC_LIB="${ROOT_DIR}/rust/manic_fitter/target/release/${LIB_NAME}"
cp "${SRC_LIB}" "${DEST_DIR}/${LIB_NAME}"
echo "Built and installed ${DEST_DIR}/${LIB_NAME}"
