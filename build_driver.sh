#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${ROOT_DIR}/src"
FORCE_BUILD=0

if [[ "${1-}" == "--force" ]]; then
  FORCE_BUILD=1
  shift
fi

if [[ -d "${ROOT_DIR}/usr/include/libusb-1.0" && -d "${ROOT_DIR}/usr/lib/x86_64-linux-gnu" ]]; then
  INCLUDE_FLAGS="-I${ROOT_DIR}/usr/include"
  LIBDIR_FLAGS="-L${ROOT_DIR}/usr/lib/x86_64-linux-gnu"
else
  INCLUDE_FLAGS="-I/usr/include"
  LIBDIR_FLAGS="-L /lib64"
fi

cd "${SRC_DIR}"
if [[ "${FORCE_BUILD}" -eq 1 ]]; then
  make -B SRC_DIR=cpp FLAGS="${INCLUDE_FLAGS} ${LIBDIR_FLAGS} -pthread" LIBS="-lusb-1.0 -ludev"
else
  make SRC_DIR=cpp FLAGS="${INCLUDE_FLAGS} ${LIBDIR_FLAGS} -pthread" LIBS="-lusb-1.0 -ludev"
fi

if [[ "${1-}" == "run" ]]; then
  sudo -E ./Linux-G13-Driver
fi
